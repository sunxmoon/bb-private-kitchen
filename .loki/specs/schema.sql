-- Database Schema for 宝宝的私房菜馆

-- 1. Users (Family Members)
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. Dishes (Library)
CREATE TABLE dishes (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    image_url VARCHAR(512),
    created_by INTEGER REFERENCES users(id),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 3. Orders (A collection of items for a meal session)
CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    status VARCHAR(50) DEFAULT 'open', -- 'open', 'completed', 'cancelled'
    created_by INTEGER REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 4. Order Items (Specific dishes within an order)
CREATE TABLE order_items (
    id SERIAL PRIMARY KEY,
    order_id INTEGER REFERENCES orders(id) ON DELETE CASCADE,
    dish_id INTEGER REFERENCES dishes(id),
    user_id INTEGER REFERENCES users(id), -- Who ordered this item
    taste TEXT,
    preferred_time TEXT,
    location TEXT,
    ingredients TEXT,
    remarks TEXT,
    custom_data JSONB, -- For extra customizable fields
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 5. Audit Logs
CREATE TABLE audit_logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    action VARCHAR(255) NOT NULL, -- 'CREATE_DISH', 'UPDATE_ORDER', 'ADD_ITEM', etc.
    table_name VARCHAR(50),
    record_id INTEGER,
    old_values JSONB,
    new_values JSONB,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Initial Data (Optional - just to seed some users)
-- INSERT INTO users (name) VALUES ('Dad'), ('Mom'), ('Child');
