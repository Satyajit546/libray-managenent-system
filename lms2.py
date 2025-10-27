import streamlit as st
import sqlite3 # CHANGED from pymysql
import pandas as pd
from datetime import date, timedelta
import os # Added for path handling

# SQLite Database File Path
DB_FILE = "lms_data.db" 

# --- 1. SESSION STATE MANAGEMENT ---

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'user_role' not in st.session_state:
    st.session_state['user_role'] = None
if 'user_id' not in st.session_state:
    st.session_state['user_id'] = None

def logout():
    """Resets the session state for logout."""
    st.session_state['logged_in'] = False
    st.session_state['user_role'] = None
    st.session_state['user_id'] = None
    st.toast("Logged out successfully!", icon="👋")
    st.rerun()

# --- 2. DATABASE CONNECTION & UTILITIES ---

@st.cache_resource
def get_db_connection():
    """Establishes and returns an SQLite database connection."""
    try:
        # Connect using the file path. check_same_thread=False is essential for Streamlit.
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        # Use row factory to access columns by name (like dictionaries)
        conn.row_factory = sqlite3.Row 
        return conn
    except Exception as e:
        st.error(f"Error connecting to SQLite: {e}")
        return None

def execute_query(query, params=(), fetch=False, commit=False):
    """Executes a SQL query and handles connection/cursor."""
    conn = get_db_connection()
    if not conn:
        return None

    try:
        with conn: # Use connection as context manager for auto-commit/rollback
            cursor = conn.cursor()
            cursor.execute(query, params)
            
            if commit:
                # Changes are committed automatically by the context manager on success
                pass
            
            if fetch:
                # Get column names (already handled by row_factory, but good for Pandas)
                data = cursor.fetchall()
                if data:
                    # Convert list of Row objects to list of dictionaries for DataFrame
                    data_dicts = [dict(row) for row in data]
                    return pd.DataFrame(data_dicts)
                return pd.DataFrame() # Return empty DataFrame if no data
            
            return True # For commit/non-fetch operations

    except sqlite3.Error as e: # CHANGED from pymysql.MySQLError
        st.error(f"Database Error: {e}")
        st.toast(f"SQL Error: {e}", icon="🚫")
        return None
        
def create_tables():
    """Initializes the SQLite database tables."""
    conn = get_db_connection()
    if not conn: return

    # Ensure the tables exist with initial data (Admin user)
    # Using """ allows multi-line SQL
    
    # 1. Admin Table
    execute_query("""
    CREATE TABLE IF NOT EXISTS Admin (
        admin_id INTEGER PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    )
    """, commit=True)

    # 2. Student Table
    execute_query("""
    CREATE TABLE IF NOT EXISTS Student (
        student_id TEXT PRIMARY KEY,
        student_name TEXT NOT NULL,
        student_pass TEXT NOT NULL
    )
    """, commit=True)
    
    # 3. Books Table
    execute_query("""
    CREATE TABLE IF NOT EXISTS Books (
        book_id INTEGER PRIMARY KEY,
        title TEXT NOT NULL,
        author TEXT NOT NULL,
        publisher TEXT,
        year INTEGER,
        copies_available INTEGER NOT NULL,
        total_copies INTEGER NOT NULL
    )
    """, commit=True)

    # 4. Issue Table
    execute_query("""
    CREATE TABLE IF NOT EXISTS IssueTable (
        issue_id INTEGER PRIMARY KEY,
        book_id INTEGER NOT NULL,
        student_id TEXT NOT NULL,
        issue_date TEXT NOT NULL,
        due_date TEXT NOT NULL,
        return_date TEXT,
        fine_amount REAL DEFAULT 0.0,
        is_returned BOOLEAN DEFAULT 0,
        FOREIGN KEY (book_id) REFERENCES Books(book_id),
        FOREIGN KEY (student_id) REFERENCES Student(student_id)
    )
    """, commit=True)

    # Insert a default Admin if one doesn't exist
    try:
        # Check if the default admin exists
        check_admin = execute_query("SELECT * FROM Admin WHERE username = ?", ("admin",), fetch=True) 
        if check_admin is None or check_admin.empty:
            execute_query("INSERT INTO Admin (username, password) VALUES (?, ?)", ("admin", "admin123"), commit=True)
            st.toast("Default Admin created: admin/admin123", icon="🔒")
    except sqlite3.Error as e:
         st.error(f"Could not initialize default admin: {e}")


# --- 3. LOGIN FUNCTIONS ---

def admin_login(username, password):
    """Handles admin login."""
    # CHANGED: Replaced %s with ? in the query
    query = "SELECT admin_id FROM Admin WHERE username = ? AND password = ?"
    result = execute_query(query, (username, password), fetch=True)

    if result is not None and not result.empty:
        st.session_state['logged_in'] = True
        st.session_state['user_role'] = 'Admin'
        st.session_state['user_id'] = result.iloc[0]['admin_id']
        st.toast(f"Welcome Admin!", icon="🚀")
        st.rerun()
    else:
        st.error("Invalid Admin Credentials")


def student_login(student_id):
    """Handles student login."""
    # CHANGED: Replaced %s with ? in the query
    query = "SELECT student_id, student_name FROM Student WHERE student_id = ?"
    result = execute_query(query, (student_id,), fetch=True)

    if result is not None and not result.empty:
        st.session_state['logged_in'] = True
        st.session_state['user_role'] = 'Student'
        st.session_state['user_id'] = result.iloc[0]['student_id']
        st.toast(f"Welcome {result.iloc[0]['student_name']}!", icon="📚")
        st.rerun()
    else:
        st.error("Invalid Student ID")

# --- 4. ADMIN PORTAL PAGES ---

# --- BOOK MANAGEMENT ---

def add_book_form():
    st.subheader("➕ Add New Book")
    with st.form("add_book_form"):
        book_id = st.number_input("Book ID", min_value=1, step=1)
        title = st.text_input("Title")
        author = st.text_input("Author")
        publisher = st.text_input("Publisher")
        year = st.number_input("Publication Year", min_value=1900, max_value=date.today().year, value=date.today().year)
        total_copies = st.number_input("Total Copies", min_value=1, step=1)

        if st.form_submit_button("Add Book", type="primary"):
            if all([book_id, title, author, total_copies]):
                # CHANGED: Replaced %s with ? in the query
                query = "INSERT INTO Books (book_id, title, author, publisher, year, copies_available, total_copies) VALUES (?, ?, ?, ?, ?, ?, ?)"
                params = (book_id, title, author, publisher, year, total_copies, total_copies)
                if execute_query(query, params, commit=True):
                    st.success(f"Book '{title}' added successfully!")
            else:
                st.warning("Please fill in all required fields.")


def view_books():
    st.subheader("📖 View and Search Books")
    search_term = st.text_input("Search by Title or Author")
    
    # SQLite LIKE searches are case-insensitive by default, but we'll use wildcards
    search_param = f"%{search_term}%"

    if search_term:
        # CHANGED: Replaced %s with ? in the query
        query = "SELECT book_id, title, author, publisher, year, copies_available FROM Books WHERE title LIKE ? OR author LIKE ?"
        params = (search_param, search_param)
    else:
        query = "SELECT book_id, title, author, publisher, year, copies_available FROM Books"
        params = ()

    df = execute_query(query, params, fetch=True)
    
    if df is not None and not df.empty:
        st.dataframe(df.set_index('book_id'), use_container_width=True)
    elif search_term:
        st.info(f"No books found matching '{search_term}'.")
    else:
        st.info("No books available in the library.")


def delete_book_form():
    st.subheader("❌ Delete Book")
    view_books() # Show current books

    with st.form("delete_book_form"):
        book_id = st.number_input("Enter Book ID to Delete", min_value=1, step=1)
        
        if st.form_submit_button("Delete Book", type="secondary"):
            if book_id:
                # CHANGED: Replaced %s with ? in the query
                query = "DELETE FROM Books WHERE book_id = ?"
                if execute_query(query, (book_id,), commit=True):
                    st.success(f"Book ID {book_id} deleted successfully.")
                    st.rerun()
                else:
                    st.error(f"Failed to delete book ID {book_id}. It might be issued.")
            else:
                st.warning("Please enter a Book ID.")

# --- USER MANAGEMENT ---

def add_student_form():
    st.subheader("🧑‍🎓 Add New Student")
    with st.form("add_student_form"):
        student_id = st.text_input("Student ID (e.g., S001)")
        student_name = st.text_input("Student Name")
        student_pass = st.text_input("Password (for retrieval)")
        
        if st.form_submit_button("Add Student", type="primary"):
            if all([student_id, student_name, student_pass]):
                # CHANGED: Replaced %s with ? in the query
                query = "INSERT INTO Student (student_id, student_name, student_pass) VALUES (?, ?, ?)"
                params = (student_id, student_name, student_pass)
                if execute_query(query, params, commit=True):
                    st.success(f"Student '{student_name}' added successfully!")
                else:
                    st.error("Student ID might already exist.")
            else:
                st.warning("Please fill in all fields.")

def add_admin_form():
    st.subheader("👑 Add New Admin")
    with st.form("add_admin_form"):
        username = st.text_input("Admin Username")
        password = st.text_input("Admin Password", type="password")
        
        if st.form_submit_button("Add Admin", type="secondary"):
            if all([username, password]):
                # CHANGED: Replaced %s with ? in the query
                query = "INSERT INTO Admin (username, password) VALUES (?, ?)"
                params = (username, password)
                if execute_query(query, params, commit=True):
                    st.success(f"Admin '{username}' added successfully!")
                else:
                    st.error("Username might already exist.")
            else:
                st.warning("Please fill in all fields.")

# --- ISSUE/RETURN MANAGEMENT ---

def issue_book_form():
    st.subheader("➡️ Issue Book")
    today = date.today().isoformat()
    due_date = (date.today() + timedelta(days=15)).isoformat()
    
    with st.form("issue_book_form"):
        book_id = st.number_input("Book ID to Issue", min_value=1, step=1)
        student_id = st.text_input("Student ID")
        
        if st.form_submit_button("Issue Book", type="primary"):
            if book_id and student_id:
                # 1. Check if book exists and is available
                # CHANGED: Replaced %s with ? in the query
                book_query = "SELECT copies_available FROM Books WHERE book_id = ?"
                book_result = execute_query(book_query, (book_id,), fetch=True)
                
                if book_result is None or book_result.empty or book_result.iloc[0]['copies_available'] <= 0:
                    st.error(f"Book ID {book_id} is not available or does not exist.")
                    return

                # 2. Check if student exists
                # CHANGED: Replaced %s with ? in the query
                student_query = "SELECT student_id FROM Student WHERE student_id = ?"
                student_result = execute_query(student_query, (student_id,), fetch=True)
                
                if student_result is None or student_result.empty:
                    st.error(f"Student ID {student_id} does not exist.")
                    return
                
                # 3. Issue the book
                # CHANGED: Replaced %s with ? in the query
                issue_query = "INSERT INTO IssueTable (book_id, student_id, issue_date, due_date, is_returned) VALUES (?, ?, ?, ?, 0)"
                issue_params = (book_id, student_id, today, due_date)
                
                if execute_query(issue_query, issue_params, commit=True):
                    # 4. Update book copy count
                    new_copies = book_result.iloc[0]['copies_available'] - 1
                    # CHANGED: Replaced %s with ? in the query
                    update_book_query = "UPDATE Books SET copies_available = ? WHERE book_id = ?"
                    execute_query(update_book_query, (new_copies, book_id), commit=True)
                    
                    st.success(f"Book ID {book_id} issued to Student {student_id}. Due: {due_date}")
                    st.balloons()
                else:
                    st.error("Failed to issue book.")

def return_book_form():
    st.subheader("⬅️ Return Book")
    today = date.today().isoformat()
    
    with st.form("return_book_form"):
        issue_id = st.number_input("Enter Issue ID to Return", min_value=1, step=1)
        
        if st.form_submit_button("Return Book", type="secondary"):
            if issue_id:
                # 1. Get issue information
                # CHANGED: Replaced %s with ? in the query
                issue_query = "SELECT book_id, due_date, is_returned FROM IssueTable WHERE issue_id = ?"
                issue_info = execute_query(issue_query, (issue_id,), fetch=True)
                
                if issue_info is None or issue_info.empty:
                    st.error(f"Issue ID {issue_id} not found.")
                    return
                
                info = issue_info.iloc[0]
                if info['is_returned']:
                    st.warning("This book has already been returned.")
                    return
                
                due_date = date.fromisoformat(info['due_date'])
                current_date = date.fromisoformat(today)
                book_id = info['book_id']
                fine = 0.0

                if current_date > due_date:
                    days_overdue = (current_date - due_date).days
                    fine = days_overdue * 5.0 # Example fine: $5.00 per day
                    st.warning(f"Book is {days_overdue} days overdue. Fine: ₹{fine:.2f}")

                # 2. Update Issue Table
                # CHANGED: Replaced %s with ? in the query
                update_issue_query = "UPDATE IssueTable SET return_date = ?, fine_amount = ?, is_returned = 1 WHERE issue_id = ?"
                issue_params = (today, fine, issue_id)
                
                if execute_query(update_issue_query, issue_params, commit=True):
                    # 3. Update book copies
                    # Get current copies available
                    book_copies_query = "SELECT copies_available FROM Books WHERE book_id = ?"
                    book_result = execute_query(book_copies_query, (book_id,), fetch=True)
                    
                    if book_result is not None and not book_result.empty:
                        new_copies = book_result.iloc[0]['copies_available'] + 1
                        # CHANGED: Replaced %s with ? in the query
                        update_book_query = "UPDATE Books SET copies_available = ? WHERE book_id = ?"
                        execute_query(update_book_query, (new_copies, book_id), commit=True)
                    
                    st.success(f"Book (Issue ID {issue_id}) returned successfully. Fine charged: ₹{fine:.2f}")
                    st.rerun()
                else:
                    st.error("Failed to process return.")
            else:
                st.warning("Please enter an Issue ID.")


# --- 5. STUDENT PORTAL PAGES ---

def student_view_issued():
    st.subheader("📚 Your Issued Books")
    student_id = st.session_state['user_id']
    
    # Query to join IssueTable and Books
    # CHANGED: Replaced %s with ? in the query
    query = """
    SELECT 
        it.issue_id, b.title, b.author, it.issue_date, it.due_date, 
        CASE WHEN it.is_returned = 0 THEN 'No' ELSE 'Yes' END AS Returned, 
        it.fine_amount
    FROM IssueTable it
    JOIN Books b ON it.book_id = b.book_id
    WHERE it.student_id = ? 
    ORDER BY it.issue_date DESC
    """
    
    df = execute_query(query, (student_id,), fetch=True)
    
    if df is not None and not df.empty:
        df['Overdue'] = df['Returned'].apply(
            lambda x: 'Yes' if x == 'No' and date.fromisoformat(df[df['Returned'] == 'No']['due_date'].iloc[0]) < date.today() else 'No'
        )
        st.dataframe(df.set_index('issue_id'), use_container_width=True)
    else:
        st.info("You currently have no recorded issue history.")


def student_view_available():
    st.subheader("🔎 Search Available Books")
    search_term = st.text_input("Search by Title or Author")
    
    search_param = f"%{search_term}%"

    if search_term:
        # CHANGED: Replaced %s with ? in the query
        query = "SELECT book_id, title, author, copies_available FROM Books WHERE copies_available > 0 AND (title LIKE ? OR author LIKE ?)"
        params = (search_param, search_param)
    else:
        query = "SELECT book_id, title, author, copies_available FROM Books WHERE copies_available > 0"
        params = ()

    df = execute_query(query, params, fetch=True)
    
    if df is not None and not df.empty:
        st.dataframe(df.set_index('book_id'), use_container_width=True)
    elif search_term:
        st.info(f"No available books found matching '{search_term}'.")
    else:
        st.info("No books are currently available.")

def student_portal():
    st.title("Welcome to the Student Portal")
    
    student_id = st.session_state['user_id']
    # CHANGED: Replaced %s with ? in the query
    query = "SELECT student_name FROM Student WHERE student_id = ?"
    name_df = execute_query(query, (student_id,), fetch=True)
    student_name = name_df.iloc[0]['student_name'] if name_df is not None and not name_df.empty else student_id

    st.markdown(f"### 👋 Hello, {student_name} ({student_id})")

    st.sidebar.subheader("Student Menu")
    student_page = st.sidebar.radio("Go to:", ["Issued Books", "Search Books"], key="student_page")
    
    if student_page == "Issued Books":
        student_view_issued()
    elif student_page == "Search Books":
        student_view_available()


def admin_portal():
    st.title("Admin Management Dashboard")
    st.sidebar.subheader("Admin Menu")
    
    admin_page = st.sidebar.radio("Go to:", [
        "View/Search Books", "Add Book", "Delete Book", 
        "Issue Book", "Return Book", 
        "Add Student", "Add Admin"
    ], key="admin_page")

    if admin_page == "View/Search Books":
        view_books()
    elif admin_page == "Add Book":
        add_book_form()
    elif admin_page == "Delete Book":
        delete_book_form()
    elif admin_page == "Issue Book":
        issue_book_form()
    elif admin_page == "Return Book":
        return_book_form()
    elif admin_page == "Add Student":
        add_student_form()
    elif admin_page == "Add Admin":
        add_admin_form()

# --- MAIN APP EXECUTION ---

def login_ui():
    """Displays the main login interface."""
    st.title("📚 Library Management System")
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("👑 Admin Login")
        st.image("https://placehold.co/400x200/4c0e66/ffffff?text=Admin+Access", use_container_width=True)
        with st.form("admin_login_form"):
            admin_user = st.text_input("Username", key="al_user", value="admin")
            admin_pass = st.text_input("Password", type="password", key="al_pass", value="admin123")
            if st.form_submit_button("Login as Admin", type="primary"):
                admin_login(admin_user, admin_pass)

    with col2:
        st.subheader("🧑‍🎓 Student Login")
        st.image("https://placehold.co/400x200/004d40/ffffff?text=Student+Access", use_container_width=True)
        with st.form("student_login_form"):
            student_id = st.text_input("Student ID (e.g., S001)", key="sl_id")
            if st.form_submit_button("Login as Student"):
                student_login(student_id)
        
        st.info("You must be added by an admin before you can log in.")


def main():
    """Main function to run the Streamlit app."""
    # Ensure tables and default admin are created on startup (or if DB file is missing)
    create_tables()

    st.set_page_config(layout="wide", page_title="Library System")

    # Sidebar for logout
    with st.sidebar:
        st.header("LMS Navigation")
        if st.session_state['logged_in']:
            st.button("Logout", on_click=logout, type="primary")
        else:
            st.info("Please log in to proceed.")
            # Simple logo/info
            st.image("https://placehold.co/150x50/f97316/ffffff?text=Library+System", use_container_width=True)
    
    # Content Area
    if not st.session_state['logged_in']:
        login_ui()
    elif st.session_state['user_role'] == 'Admin':
        admin_portal()
    elif st.session_state['user_role'] == 'Student':
        student_portal()


if __name__ == '__main__':
    main()
