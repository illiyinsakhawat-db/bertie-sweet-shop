# Normalised schema (3NF) – entity relationship diagram

GitHub renders this Mermaid diagram automatically. The original hand-drawn conceptual ERD is in [`erd_original.jpg`](erd_original.jpg).

```mermaid
erDiagram
    REGION ||--|| WAREHOUSE : "has one"
    WAREHOUSE ||--|{ DISTRIBUTION_CENTRE : supplies
    REGION ||--o{ DELIVERY_ADDRESS : "located in"

    SWEET_CATEGORY ||--|{ SWEET : groups
    SWEET ||--o{ MULTI_PACK_ITEM : "packed in"
    MULTI_PACK ||--|{ MULTI_PACK_ITEM : contains
    SWEET ||--o{ SWEET_OFFER : "promoted by"
    OFFER ||--o{ SWEET_OFFER : applies
    DISTRIBUTION_CENTRE ||--o{ STOCK : holds
    SWEET ||--o{ STOCK : "stocked as"

    CUSTOMER ||--|{ DELIVERY_ADDRESS : has
    CUSTOMER ||--|{ PAYMENT_METHOD : has
    CUSTOMER ||--o{ SHOPPING_LIST : saves
    SHOPPING_LIST ||--|{ SHOPPING_LIST_ITEM : contains
    CUSTOMER ||--o{ SHOPPING_BASKET : fills
    SHOPPING_BASKET ||--|{ BASKET_ITEM : contains

    CUSTOMER ||--o{ CUSTOMER_ORDER : places
    SHOPPING_BASKET |o--o| CUSTOMER_ORDER : "checks out as"
    DISTRIBUTION_CENTRE ||--o{ CUSTOMER_ORDER : fulfils
    DELIVERY_ADDRESS ||--o{ CUSTOMER_ORDER : "delivered to"
    PAYMENT_METHOD ||--o{ CUSTOMER_ORDER : "paid with"
    CUSTOMER_ORDER ||--|{ ORDER_ITEM : contains
    SWEET |o--o{ ORDER_ITEM : "sold as"
    MULTI_PACK |o--o{ ORDER_ITEM : "sold as"

    CUSTOMER ||--o{ SPECIAL_ORDER : places
    SPECIAL_ORDER ||--|{ SPECIAL_ORDER_ITEM : contains
    CUSTOMER ||--o{ STANDING_ORDER : "sets up"
    STANDING_ORDER ||--|{ STANDING_ORDER_ITEM : contains

    REGION { smallint region_id PK
             varchar region_name }
    WAREHOUSE { smallint warehouse_id PK
                smallint region_id FK "UNIQUE" }
    DISTRIBUTION_CENTRE { smallint dc_id PK
                          smallint warehouse_id FK }
    SWEET_CATEGORY { smallint category_id PK
                     varchar category_name }
    SWEET { varchar sweet_code PK
            varchar sweet_name
            smallint size_grams
            numeric unit_price
            smallint category_id FK }
    MULTI_PACK { smallint multi_pack_id PK
                 numeric multi_pack_price }
    MULTI_PACK_ITEM { smallint multi_pack_id PK, FK
                      varchar sweet_code PK, FK
                      smallint quantity }
    OFFER { smallint offer_id PK
            numeric discount_pct }
    SWEET_OFFER { varchar sweet_code PK, FK
                  smallint offer_id PK, FK
                  date offer_start_date PK
                  date offer_end_date }
    STOCK { smallint dc_id PK, FK
            varchar sweet_code PK, FK
            int quantity_on_hand
            int reorder_level }
    CUSTOMER { int customer_id PK
               varchar username "UNIQUE"
               varchar email "UNIQUE"
               char password_hash }
    DELIVERY_ADDRESS { int address_id PK
                       int customer_id FK
                       smallint region_id FK }
    PAYMENT_METHOD { int payment_method_id PK
                     int customer_id FK
                     char card_last4
                     varchar payment_token }
    CUSTOMER_ORDER { int order_id PK
                     int customer_id FK
                     int basket_id FK
                     smallint dc_id FK
                     int address_id FK
                     int payment_method_id FK
                     date order_date
                     numeric delivery_charge }
    ORDER_ITEM { int order_item_id PK
                 int order_id FK
                 varchar sweet_code FK "nullable"
                 smallint multi_pack_id FK "nullable"
                 smallint quantity
                 numeric unit_price
                 numeric discount_pct }
```

> `ORDER_ITEM`, `BASKET_ITEM`, `SHOPPING_LIST_ITEM`, `SPECIAL_ORDER_ITEM` and `STANDING_ORDER_ITEM` each reference **either** a sweet **or** a multi-pack, enforced with `CHECK (num_nonnulls(sweet_code, multi_pack_id) = 1)`.
