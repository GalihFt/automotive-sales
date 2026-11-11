CREATE SCHEMA IF NOT EXISTS automotive;


SELECT (5);


CREATE TABLE automotive.dealers (
    dealer_id VARCHAR(10) PRIMARY KEY,
    dealer_name VARCHAR(100) NOT NULL,
    city VARCHAR(50) NOT NULL,
    region VARCHAR(50) NOT NULL
    );

CREATE TABLE automotive.vehicles (
    vehicle_id VARCHAR(10) PRIMARY KEY,
    brand VARCHAR(50) NOT NULL,
    model VARCHAR(50) NOT NULL,
    category VARCHAR(50) NOT NULL,
    list_price INTEGER NOT NULL,

    CONSTRAINT chk_price_vehicle
        CHECK(list_price > 0)
);

CREATE TABLE automotive.inventory (
    snapshot_date DATE NOT NULL,
    dealer_id VARCHAR(10) NOT NULL,
    vehicle_id VARCHAR(10) NOT NULL,
    stock_qty INTEGER NOT NULL DEFAULT 0,

    CONSTRAINT pk_inventory
        PRIMARY KEY (snapshot_date, dealer_id, vehicle_id),

    CONSTRAINT fk_inventory_dealer
        FOREIGN KEY (dealer_id)
        REFERENCES automotive.dealers(dealer_id),

    CONSTRAINT fk_inventory_vehicle
        FOREIGN KEY (vehicle_id)
        REFERENCES automotive.vehicles(vehicle_id),
    
    CONSTRAINT chk_stock_qty
        CHECK (stock_qty >= 0)
);


CREATE TABLE automotive.sales (
    order_id VARCHAR(50) PRIMARY KEY,
    order_date DATE NOT NULL,
    dealer_id VARCHAR(10) NOT NULL,
    vehicle_id VARCHAR(10) NOT NULL,
    qty SMALLINT NOT NULL,
    unit_price NUMERIC(20,2) NOT NULL,
    status VARCHAR(20) NOT NULL,
    updated_at TIMESTAMP,

    CONSTRAINT fk_sales_dealer
        FOREIGN KEY (dealer_id)
        REFERENCES automotive.dealers(dealer_id),
    
    CONSTRAINT fk_sales_vehicle
        FOREIGN KEY (vehicle_id)
        REFERENCES automotive.vehicles(vehicle_id),
    
    CONSTRAINT chk_sales_qty
        CHECK(qty > 0),
    
    CONSTRAINT chk_unit_price
        CHECK(unit_price > 0)
);