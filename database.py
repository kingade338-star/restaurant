import sqlite3
from datetime import datetime
from typing import Optional, List, Dict, Any

DB_FILE = 'iya_meta.db'

def init_db():
    """Initialize database with all tables"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Orders table
    c.execute('''CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        phone TEXT NOT NULL,
        customer_name TEXT,
        items TEXT NOT NULL,
        total INTEGER NOT NULL,
        status TEXT DEFAULT 'pending',
        payment_status TEXT DEFAULT 'unpaid',
        delivery_address TEXT,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Complaints table
    c.execute('''CREATE TABLE IF NOT EXISTS complaints (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        phone TEXT NOT NULL,
        customer_name TEXT,
        category TEXT NOT NULL,
        description TEXT NOT NULL,
        status TEXT DEFAULT 'open',
        priority TEXT DEFAULT 'medium',
        resolution_notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        resolved_at TIMESTAMP
    )''')
    
    # Customers table
    c.execute('''CREATE TABLE IF NOT EXISTS customers (
        phone TEXT PRIMARY KEY,
        name TEXT,
        address TEXT,
        email TEXT,
        conversation_state TEXT,
        total_orders INTEGER DEFAULT 0,
        total_spent INTEGER DEFAULT 0,
        last_order_date TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Messages log (for audit trail)
    c.execute('''CREATE TABLE IF NOT EXISTS message_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        phone TEXT NOT NULL,
        direction TEXT NOT NULL,  -- 'incoming' or 'outgoing'
        message TEXT NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    conn.commit()
    conn.close()
    print(f"✅ Database initialized: {DB_FILE}")

# ============ ORDERS ============

def save_order(phone: str, items: str, total: int, customer_name: str = None, address: str = None) -> int:
    """Save new order and return order ID"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute('''INSERT INTO orders (phone, customer_name, items, total, delivery_address) 
                 VALUES (?, ?, ?, ?, ?)''', 
              (phone, customer_name, items, total, address))
    conn.commit()
    order_id = c.lastrowid
    
    # Update customer stats
    c.execute('''INSERT INTO customers (phone, name, address, total_orders, total_spent, last_order_date, last_active)
                 VALUES (?, ?, ?, 1, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                 ON CONFLICT(phone) DO UPDATE SET
                 name=COALESCE(EXCLUDED.name, customers.name),
                 address=COALESCE(EXCLUDED.address, customers.address),
                 total_orders=total_orders+1,
                 total_spent=total_spent+EXCLUDED.total_spent,
                 last_order_date=CURRENT_TIMESTAMP,
                 last_active=CURRENT_TIMESTAMP''',
              (phone, customer_name, address, total))
    
    conn.commit()
    conn.close()
    return order_id # type: ignore

def get_all_orders(status: str = None, limit: int = 100) -> List[Dict]:
    """Get all orders with optional filter"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    if status:
        c.execute('''SELECT * FROM orders WHERE status = ? ORDER BY created_at DESC LIMIT ?''', 
                  (status, limit))
    else:
        c.execute('''SELECT * FROM orders ORDER BY created_at DESC LIMIT ?''', (limit,))
    
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_order_by_id(order_id: int) -> Optional[Dict]:
    """Get single order details"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM orders WHERE id = ?', (order_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None
def update_order_status(order_id: int, status: str, notes: Optional[str] = None):
    """Update order status (pending → preparing → ready → delivered)"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''UPDATE orders SET status = ?, notes = COALESCE(?, notes), updated_at = CURRENT_TIMESTAMP 
                 WHERE id = ?''', (status, notes, order_id))
    conn.commit()
    conn.close()

def get_order_stats() -> Dict:
    """Get dashboard statistics"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    stats = {}
    
    # Total orders
    c.execute('SELECT COUNT(*), SUM(total) FROM orders')
    result = c.fetchone()
    stats['total_orders'] = result[0] or 0
    stats['total_revenue'] = result[1] or 0
    
    # By status
    c.execute('''SELECT status, COUNT(*) FROM orders GROUP BY status''')
    stats['status_breakdown'] = dict(c.fetchall())
    
    # Today's orders
    c.execute('''SELECT COUNT(*), SUM(total) FROM orders 
                 WHERE date(created_at) = date('now')''')
    result = c.fetchone()
    stats['today_orders'] = result[0] or 0
    stats['today_revenue'] = result[1] or 0
    
    conn.close()
    return stats

# ============ COMPLAINTS ============

def save_complaint(phone: str, category: str, description: str, customer_name: str = None) -> int:
    """Save complaint and return complaint ID"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute('''INSERT INTO complaints (phone, customer_name, category, description) 
                 VALUES (?, ?, ?, ?)''', (phone, customer_name, category, description))
    conn.commit()
    complaint_id = c.lastrowid
    conn.close()
    return complaint_id # type: ignore

def get_all_complaints(status: str = None) -> List[Dict]:
    """Get all complaints"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    if status:
        c.execute('''SELECT * FROM complaints WHERE status = ? ORDER BY created_at DESC''', (status,))
    else:
        c.execute('''SELECT * FROM complaints ORDER BY created_at DESC''')
    
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def update_complaint_status(complaint_id: int, status: str, resolution: str = None):
    """Update complaint status"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    if status == 'resolved':
        c.execute('''UPDATE complaints SET status = ?, resolution_notes = ?, resolved_at = CURRENT_TIMESTAMP 
                     WHERE id = ?''', (status, resolution, complaint_id))
    else:
        c.execute('''UPDATE complaints SET status = ?, resolution_notes = ? WHERE id = ?''',
                  (status, resolution, complaint_id))
    
    conn.commit()
    conn.close()

# ============ CUSTOMERS ============

def get_all_customers() -> List[Dict]:
    """Get all customers with stats"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('''SELECT * FROM customers ORDER BY last_active DESC''')
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_customer_by_phone(phone: str) -> Optional[Dict]:
    """Get single customer details"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM customers WHERE phone = ?', (phone,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def get_customer_history(phone: str) -> Dict:
    """Get customer's order and complaint history"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # Orders
    c.execute('SELECT * FROM orders WHERE phone = ? ORDER BY created_at DESC', (phone,))
    orders = [dict(row) for row in c.fetchall()]
    
    # Complaints
    c.execute('SELECT * FROM complaints WHERE phone = ? ORDER BY created_at DESC', (phone,))
    complaints = [dict(row) for row in c.fetchall()]
    
    conn.close()
    return {'orders': orders, 'complaints': complaints}

# ============ CONVERSATION STATE ============

def update_customer_state(phone: str, state: str):
    """Save conversation state"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''INSERT INTO customers (phone, conversation_state, last_active)
                 VALUES (?, ?, CURRENT_TIMESTAMP)
                 ON CONFLICT(phone) DO UPDATE SET
                 conversation_state=EXCLUDED.conversation_state,
                 last_active=CURRENT_TIMESTAMP''', (phone, state))
    conn.commit()
    conn.close()

def get_customer_state(phone: str) -> Optional[str]:
    """Get conversation state"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT conversation_state FROM customers WHERE phone = ?', (phone,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else None

# ============ MESSAGE LOGGING ============

def log_message(phone: str, direction: str, message: str):
    """Log all messages for audit trail"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('INSERT INTO message_logs (phone, direction, message) VALUES (?, ?, ?)',
              (phone, direction, message))
    conn.commit()
    conn.close()

def get_message_logs(phone: str = None, limit: int = 100) -> List[Dict]:
    """Get message logs"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    if phone:
        c.execute('''SELECT * FROM message_logs WHERE phone = ? ORDER BY timestamp DESC LIMIT ?''',
                  (phone, limit))
    else:
        c.execute('''SELECT * FROM message_logs ORDER BY timestamp DESC LIMIT ?''', (limit,))
    
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]