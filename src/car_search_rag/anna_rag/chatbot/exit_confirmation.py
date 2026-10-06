"""종료 확인은 브라우저에서 열고, 실제 종료만 서버로 전달합니다.

열기/취소에는 Streamlit 재실행이 없어 대화·이미지·스크롤 위치가 유지됩니다.
사용자 메시지는 HTML에 넣지 않고 대화 존재 여부만 전달합니다.
"""
import streamlit.components.v2 as components

EXIT_CONFIRMATION_JS = r"""
export default function(component) {
  const {data, setTriggerValue} = component;
  let overlay = null;
  let previousFocus = null;
  let locks = [];
  let keyHandler = null;
  let appRoot = null;
  let previousInert = false;
  function close(restoreFocus = true) {
    if (!overlay) return;
    overlay.remove(); overlay = null;
    document.documentElement.classList.remove('chat-exit-confirming');
    if(appRoot) appRoot.inert=previousInert;
    document.removeEventListener('keydown', keyHandler, true);
    locks.forEach(({el, top, left, overflow, stopScroll}) => {
      el.removeEventListener('scroll', stopScroll);
      el.style.overflow = overflow;
      el.scrollTop = top; el.scrollLeft = left;
    });
    locks = [];
    if (restoreFocus && previousFocus?.isConnected) previousFocus.focus({preventScroll:true});
  }
  function open() {
    if (overlay) return;
    previousFocus = document.activeElement;
    appRoot=document.querySelector('.stApp');
    if(appRoot){previousInert=appRoot.inert;appRoot.inert=true;}
    document.querySelectorAll('[data-testid="stMain"], [data-testid="stAppScrollToBottomContainer"], [data-testid="stSidebarContent"], html, body').forEach(el => {
      const top=el.scrollTop, left=el.scrollLeft, overflow=el.style.overflow;
      const stopScroll=()=>{el.scrollTop=top;el.scrollLeft=left;};
      locks.push({el,top,left,overflow,stopScroll});
      el.style.overflow='hidden';
      el.addEventListener('scroll',stopScroll);
    });
    document.documentElement.classList.add('chat-exit-confirming');
    overlay=document.createElement('div');
    overlay.className='chat-exit-overlay';
    overlay.innerHTML=`<section class="chat-exit-dialog" role="dialog" aria-modal="true" aria-labelledby="chat-exit-title" aria-describedby="chat-exit-description" tabindex="-1">
      <h2 id="chat-exit-title">챗봇을 종료하시겠어요?</h2>
      <p id="chat-exit-description">챗봇을 종료하면 기존 대화가 삭제되요.</p>
      <div class="chat-exit-actions"><button type="button" data-action="cancel">취소</button><button type="button" data-action="exit">종료</button></div>
    </section>`;
    document.body.appendChild(overlay);
    const cancel=overlay.querySelector('[data-action="cancel"]');
    const exit=overlay.querySelector('[data-action="exit"]');
    cancel.onclick=()=>close();
    exit.onclick=()=>{close(false);setTriggerValue('confirmed',true);};
    overlay.addEventListener('wheel',e=>e.preventDefault(),{passive:false});
    overlay.addEventListener('touchmove',e=>e.preventDefault(),{passive:false});
    keyHandler=(e)=>{
      if(e.key==='Escape'){e.preventDefault();e.stopImmediatePropagation();close();}
      else if(e.key==='Tab'){
        e.preventDefault();
        (document.activeElement===cancel ? exit : cancel).focus({preventScroll:true});
      }else if(['PageDown','PageUp','Home','End','ArrowDown','ArrowUp',' '].includes(e.key) && !overlay.contains(document.activeElement)){
        e.preventDefault();
      }
    };
    document.addEventListener('keydown',keyHandler,true);
    cancel.focus({preventScroll:true});
  }
  // React가 버튼 클릭을 서버로 보내기 전에 브라우저에서 처리합니다.
  const intercept=(e)=>{
    if(!e.target.closest?.('.st-key-back_to_vehicles button')) return;
    const hasMessages = document.querySelector('.st-key-chat_history [data-testid="stChatMessage"]');
    if(!data.hasConversation && !hasMessages) return;
    e.preventDefault();e.stopImmediatePropagation();open();
  };
  document.addEventListener('click',intercept,true);
  return ()=>{document.removeEventListener('click',intercept,true);close(false);};
}
"""

EXIT_CONFIRMATION_CSS = """
html.chat-exit-confirming [data-testid="stMain"],
html.chat-exit-confirming [data-testid="stAppScrollToBottomContainer"],
html.chat-exit-confirming [data-testid="stSidebarContent"] {scroll-behavior:auto!important;}
html.chat-exit-confirming .stApp {pointer-events:none;}
html.chat-exit-confirming .stApp * {animation-play-state:paused!important;}
.chat-exit-overlay {
 position:fixed;inset:0;z-index:2147483647;background:rgba(25,22,38,.35);
 display:flex;align-items:center;justify-content:center;padding:24px;
 overscroll-behavior:contain;font-family:"Pretendard Variable",sans-serif;
}
.chat-exit-dialog {width:440px;max-width:100%;padding:28px;border-radius:20px;
 background:#fff;box-shadow:0 16px 60px #21193626;color:#21212b;outline:none;}
.chat-exit-dialog h2 {font-family:inherit;font-size:22px!important;font-weight:700;
 line-height:1.4;margin:0 0 14px!important;padding:0!important;}
.chat-exit-dialog p {font-family:inherit;font-size:16px;line-height:1.6;margin:0 0 26px;color:#625d70;}
.chat-exit-actions {display:flex;gap:10px;}
.chat-exit-actions button {flex:1;min-height:46px;border-radius:12px;border:1px solid #dedbe5;
 background:#fff;color:#484356;font:600 15px "Pretendard Variable",sans-serif;cursor:pointer;}
.chat-exit-actions button[data-action="exit"] {background:#5b43e8;border-color:#5b43e8;color:white;}
.chat-exit-actions button:focus-visible {outline:2px solid #a99aec;outline-offset:3px;}
"""

def exit_confirmation(**kwargs):
    # 현재 Streamlit 런타임에 등록합니다(테스트도 앱마다 별도 런타임).
    render = components.component(
        'chat_exit_confirmation', js=EXIT_CONFIRMATION_JS,
        css=EXIT_CONFIRMATION_CSS, isolate_styles=False,
    )
    return render(**kwargs)
