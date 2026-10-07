"""빠르게 생성된 긴 답변 때문에 화면 출력이 수십 초 밀리지 않게 합니다."""
import unittest

from car_search_rag.anna_rag.chatbot.answer_view import take_stream_chunk


class StreamPacingTests(unittest.TestCase):
    def test_completed_backlog_drains_in_twelve_frames_without_losing_text(self):
        for text in ('', '짧은 답', '첫 줄\n둘째 줄 [S1] ' * 250):
            job = {'text': '이미 보인 글 ', 'buffer': text}
            frames = 0
            while job['buffer']:
                take_stream_chunk(job, complete=True)
                frames += 1
            self.assertLessEqual(frames, 12)
            self.assertEqual(job['text'], '이미 보인 글 ' + text)

    def test_incoming_chunks_remain_in_order_and_catch_up_on_completion(self):
        pieces = ['안녕하세요. ', '설명서 내용을 안내합니다.\n' * 40, '[S1]']
        job = {'text': '', 'buffer': ''}
        for piece in pieces:
            job['buffer'] += piece
            take_stream_chunk(job)
        self.assertTrue(job['buffer'])  # 생성 중에는 한꺼번에 튀어나오지 않습니다.
        frames = 0
        while job['buffer']:
            take_stream_chunk(job, complete=True)
            frames += 1
        self.assertLessEqual(frames, 12)
        self.assertEqual(job['text'], ''.join(pieces))


if __name__ == '__main__':
    unittest.main()
