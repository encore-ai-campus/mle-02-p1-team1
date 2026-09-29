-- name: create_temp_table!
CREATE TEMP TABLE transaction_demo_items (
    item_id integer PRIMARY KEY,
    item_name text NOT NULL
) ON COMMIT DROP;

-- name: insert_item!
INSERT INTO transaction_demo_items (item_id, item_name)
VALUES (:item_id, :item_name);

-- name: select_items
SELECT item_id, item_name
FROM transaction_demo_items
ORDER BY item_id;
