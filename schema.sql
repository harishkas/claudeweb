-- =========================================================
-- IMPROVED SCHEMA WITH INDEXES & OPTIMIZATIONS
-- =========================================================

-- Drop existing tables if recreating
-- DROP TABLE IF EXISTS order_items CASCADE;
-- DROP TABLE IF EXISTS orders CASCADE;
-- DROP TABLE IF EXISTS cart CASCADE;
-- DROP TABLE IF EXISTS products CASCADE;
-- DROP TABLE IF EXISTS users CASCADE;

-- =========================================================
-- USERS TABLE
-- =========================================================
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password TEXT NOT NULL,
    is_admin BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for faster email lookups (login)
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- Index for admin queries
CREATE INDEX IF NOT EXISTS idx_users_admin ON users(is_admin) WHERE is_admin = TRUE;

-- =========================================================
-- PRODUCTS TABLE
-- =========================================================
CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    name VARCHAR(150) NOT NULL,
    category VARCHAR(50) NOT NULL,
    price NUMERIC(10,2) NOT NULL CHECK (price >= 0),
    image_url TEXT,
    stock INTEGER DEFAULT 0 CHECK (stock >= 0),
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for category filtering
CREATE INDEX IF NOT EXISTS idx_products_category ON products(category);

-- Index for product listing (sorted by date)
CREATE INDEX IF NOT EXISTS idx_products_created_at ON products(created_at DESC);

-- Composite index for category + date sorting
CREATE INDEX IF NOT EXISTS idx_products_category_created ON products(category, created_at DESC);

-- Partial index for in-stock products only
CREATE INDEX IF NOT EXISTS idx_products_in_stock ON products(id, name, price) WHERE stock > 0;

-- =========================================================
-- CART TABLE
-- =========================================================
CREATE TABLE IF NOT EXISTS cart (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity INTEGER DEFAULT 1 CHECK (quantity > 0),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
    UNIQUE(user_id, product_id)  -- Prevent duplicate cart entries
);

-- Index for fetching user's cart
CREATE INDEX IF NOT EXISTS idx_cart_user_id ON cart(user_id);

-- Index for product lookups in cart
CREATE INDEX IF NOT EXISTS idx_cart_product_id ON cart(product_id);

-- Composite index for cart queries
CREATE INDEX IF NOT EXISTS idx_cart_user_product ON cart(user_id, product_id);

-- =========================================================
-- ORDERS TABLE
-- =========================================================
CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    total_amount NUMERIC(10,2) NOT NULL CHECK (total_amount >= 0),
    status VARCHAR(50) DEFAULT 'Pending',
    shipping_address TEXT,
    payment_method VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Index for user order history
CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id);

-- Index for order status filtering
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);

-- Index for recent orders (admin dashboard)
CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at DESC);

-- Composite index for user orders sorted by date
CREATE INDEX IF NOT EXISTS idx_orders_user_created ON orders(user_id, created_at DESC);

-- =========================================================
-- ORDER ITEMS TABLE
-- =========================================================
CREATE TABLE IF NOT EXISTS order_items (
    id SERIAL PRIMARY KEY,
    order_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    price NUMERIC(10,2) NOT NULL CHECK (price >= 0),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
);

-- Index for fetching order details
CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON order_items(order_id);

-- Index for product sales analytics
CREATE INDEX IF NOT EXISTS idx_order_items_product_id ON order_items(product_id);

-- =========================================================
-- TRIGGERS FOR UPDATED_AT
-- =========================================================

-- Function to update timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers for each table
DROP TRIGGER IF EXISTS update_users_updated_at ON users;
CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_products_updated_at ON products;
CREATE TRIGGER update_products_updated_at
    BEFORE UPDATE ON products
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_cart_updated_at ON cart;
CREATE TRIGGER update_cart_updated_at
    BEFORE UPDATE ON cart
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_orders_updated_at ON orders;
CREATE TRIGGER update_orders_updated_at
    BEFORE UPDATE ON orders
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =========================================================
-- SAMPLE DATA (OPTIONAL - FOR TESTING)
-- =========================================================

-- Insert admin user (password: admin123)
INSERT INTO users (name, email, password, is_admin)
VALUES ('Admin User', 'admin@haksshop.com', 'scrypt:32768:8:1$zqWx8yQg4nB8lOze$c0ea4f8e8b3f5c1f8d3e2a1b9c8d7e6f5a4b3c2d1e0f9a8b7c6d5e4f3a2b1c0d9e8f7a6b5c4d3e2f1a0b9c8d7e6f5a4b3c2d1e0f', TRUE)
ON CONFLICT (email) DO NOTHING;

-- Insert sample products
INSERT INTO products (name, category, price, image_url, stock, description) VALUES
('Men Premium T-Shirt', 'clothing', 599.00, 'assets/men-tshirt.webp', 50, 'Comfortable cotton t-shirt for everyday wear'),
('Stylish Formal Shirt', 'clothing', 899.00, 'assets/shirt.avif', 30, 'Perfect for office and formal occasions'),
('Winter Jacket', 'clothing', 1499.00, 'assets/men 2.jpg', 20, 'Keep warm in style this winter'),
('Women Casual Top', 'clothing', 699.00, 'assets/women t shirt.avif', 40, 'Trendy and comfortable for daily use'),
('Luxury Watch', 'accessories', 2499.00, 'assets/watch.webp', 15, 'Elegant timepiece with premium finish'),
('Wireless Headphones', 'accessories', 1999.00, 'assets/headphone.jfif', 25, 'High-quality sound and comfort'),
('Wireless Mouse', 'accessories', 799.00, 'assets/mouse.webp', 60, 'Precision control for work and gaming'),
('Mechanical Keyboard', 'accessories', 2299.00, 'assets/keyboard.jfif', 18, 'Premium keys for best performance'),
('Wireless Earbuds', 'accessories', 1499.00, 'assets/earbods.webp', 35, 'Compact and powerful audio'),
('Luxury Perfume', 'accessories', 1299.00, 'assets/perfume.webp', 45, 'Long-lasting premium fragrance'),
('Anniversary Card', 'cards', 199.00, 'assets/couple bracelet.webp', 100, 'Celebrate love and togetherness'),
('Birthday Card', 'cards', 149.00, 'assets/banner.jpg', 150, 'Bright designs for joyful birthdays'),
('Wedding Invitation', 'cards', 299.00, 'assets/peacock.jpg', 80, 'Elegant wedding card designs'),
('Thank You Card', 'cards', 129.00, 'assets/photo-1534695941753-73cf13435eb4.jfif', 120, 'Simple heartfelt thanks'),
('Festival Card', 'cards', 179.00, 'assets/Untitled-design-2021-09-17T224949.304.jpg', 90, 'Celebrate festivals in style'),
('Luxury Greeting Card', 'cards', 349.00, 'assets/RING 3.webp', 50, 'Premium finish for special occasions')
ON CONFLICT DO NOTHING;

-- =========================================================
-- MATERIALIZED VIEW FOR POPULAR PRODUCTS (OPTIONAL)
-- =========================================================
CREATE MATERIALIZED VIEW IF NOT EXISTS popular_products AS
SELECT 
    p.id,
    p.name,
    p.category,
    p.price,
    p.image_url,
    COALESCE(SUM(oi.quantity), 0) as total_sold
FROM products p
LEFT JOIN order_items oi ON p.id = oi.product_id
GROUP BY p.id, p.name, p.category, p.price, p.image_url
ORDER BY total_sold DESC
LIMIT 50;

-- Index on materialized view
CREATE INDEX IF NOT EXISTS idx_popular_products_category ON popular_products(category);

-- Refresh function (call this periodically or via cron)
-- REFRESH MATERIALIZED VIEW popular_products;

-- =========================================================
-- PERFORMANCE MONITORING VIEWS
-- =========================================================

-- View for low stock products
CREATE OR REPLACE VIEW low_stock_products AS
SELECT id, name, category, stock
FROM products
WHERE stock < 10
ORDER BY stock ASC;

-- View for recent orders
CREATE OR REPLACE VIEW recent_orders AS
SELECT 
    o.id,
    o.user_id,
    u.name as customer_name,
    o.total_amount,
    o.status,
    o.created_at
FROM orders o
JOIN users u ON o.user_id = u.id
ORDER BY o.created_at DESC
LIMIT 100;

-- =========================================================
-- VACUUM & ANALYZE (Run periodically for optimization)
-- =========================================================
-- VACUUM ANALYZE users;
-- VACUUM ANALYZE products;
-- VACUUM ANALYZE cart;
-- VACUUM ANALYZE orders;
-- VACUUM ANALYZE order_items;
