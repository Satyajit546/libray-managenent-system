import streamlit as st
import sqlite3
import pandas as pd
from datetime import date, timedelta

# Default database credentials
DB_HOST = "localhost"
DB_USER = "root"
DB_PASSWORD = "Satyajit546@"
DB_NAME = "lms"

# --- 2. DATABASE CONNECTION & UTILITES ---

@st.cache_resource
def get_db_connection():
    """Establishes and returns a MySQL database connection."""
    try:
        conn = pymysql.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        return conn
    except Exception as e:
        st.error(f"Error connecting to MySQL: {e}")
        return None

def execute_query(query, params=None, fetch=False, commit=False):
    """Executes a SQL query and handles connection/cursor."""
    conn = get_db_connection()
    if not conn:
        return None

    try:
        with conn.cursor() as cursor:
            cursor.execute(query, params)
            if commit:
                conn.commit()
            if fetch:
                # Get column names
                columns = [col[0] for col in cursor.description]
                # Get data rows
                data = cursor.fetchall()
                # Return as pandas DataFrame for easy display
                return pd.DataFrame(data, columns=columns)
            return cursor.rowcount
    except pymysql.MySQLError as e:
        st.error(f"Database Error: {e}")
        return None
    finally:
        # Note: Connection is managed by st.cache_resource, but explicit close is safe
        # However, for pymysql and st.cache_resource, returning the connection is standard.
        pass

# --- 3. STATE MANAGEMENT (LOGIN) ---

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'user_role' not in st.session_state:
    st.session_state['user_role'] = None
if 'user_id' not in st.session_state:
    st.session_state['user_id'] = None

# --- 4. AUTHENTICATION FUNCTIONS ---

def admin_login(username, password):
    """Authenticates admin credentials."""
    query = "SELECT admin_id FROM Admin WHERE username = %s AND password = %s"
    df = execute_query(query, (username, password), fetch=True)
    if df is not None and not df.empty:
        st.session_state['logged_in'] = True
        st.session_state['user_role'] = 'admin'
        st.session_state['user_id'] = df.iloc[0]['admin_id']
        st.success("Admin login successful!")
        st.rerun()
    else:
        st.error("Invalid Admin Username or Password.")

def student_login(student_id):
    """Authenticates student ID."""
    query = "SELECT student_id, name FROM Student WHERE student_id = %s"
    df = execute_query(query, (student_id,), fetch=True)
    if df is not None and not df.empty:
        st.session_state['logged_in'] = True
        st.session_state['user_role'] = 'student'
        st.session_state['user_id'] = df.iloc[0]['student_id']
        st.success(f"Welcome, {df.iloc[0]['name']}!")
        st.rerun()
    else:
        st.error("Invalid Student ID.")

def logout():
    """Resets session state for logout."""
    st.session_state['logged_in'] = False
    st.session_state['user_role'] = None
    st.session_state['user_id'] = None
    st.info("Logged out successfully.")
    st.rerun()

# --- 5. ADMIN PORTAL FUNCTIONS (CRUD) ---

def add_book_form():
    """Form to add a new book."""
    st.subheader("Add New Book")
    with st.form("add_book_form"):
        title = st.text_input("Title", key="book_title")
        author = st.text_input("Author", key="book_author")
        genre = st.text_input("Genre", key="book_genre")
        isbn = st.text_input("ISBN (Unique)", key="book_isbn")
        total_copies = st.number_input("Total Copies", min_value=1, step=1, key="book_total")
        submitted = st.form_submit_button("Add Book")

        if submitted:
            if title and total_copies > 0:
                query = """
                INSERT INTO Books (title, author, genre, isbn, total_copies, available_copies)
                VALUES (%s, %s, %s, %s, %s, %s)
                """
                params = (title, author, genre, isbn, total_copies, total_copies)
                if execute_query(query, params, commit=True) is not None:
                    st.success(f"Book '{title}' added successfully with {total_copies} copies.")
                else:
                    st.error("Failed to add book. Check if ISBN already exists.")
            else:
                st.warning("Please fill in the title and ensure copies > 0.")

def view_books(search_term=""):
    """Displays books based on an optional search term."""
    st.subheader("Book Inventory")
    if search_term:
        query = "SELECT * FROM Books WHERE title LIKE %s OR author LIKE %s OR isbn LIKE %s"
        params = (f"%{search_term}%", f"%{search_term}%", f"%{search_term}%")
    else:
        query = "SELECT * FROM Books"
        params = None

    df_books = execute_query(query, params, fetch=True)
    if df_books is not None and not df_books.empty:
        st.dataframe(df_books, use_container_width=True)
    elif not search_term:
        st.info("No books in the inventory.")

def delete_book_form():
    """Form to delete a book."""
    st.subheader("Delete Book")
    book_id = st.number_input("Enter Book ID to Delete", min_value=1, step=1)
    if st.button("Delete Book", key="delete_book_btn"):
        if book_id:
            query = "DELETE FROM Books WHERE book_id = %s"
            if execute_query(query, (book_id,), commit=True) > 0:
                st.success(f"Book with ID {book_id} deleted successfully.")
            else:
                st.error(f"Book with ID {book_id} not found or failed to delete.")

def add_student_form():
    """Form to add a new student."""
    st.subheader("Add New Student")
    with st.form("add_student_form"):
        student_id = st.text_input("Student Registration ID (e.g., S001)", help="Must be unique. Recommended: use format 'S' + unique number.")
        name = st.text_input("Student Name")
        contact = st.text_input("Contact Number")
        submitted = st.form_submit_button("Add Student")

        if submitted:
            if student_id and name:
                query = "INSERT INTO Student (student_id, name, contact) VALUES (%s, %s, %s)"
                params = (student_id, name, contact)
                if execute_query(query, params, commit=True) is not None:
                    st.success(f"Student '{name}' added successfully with ID: {student_id}")
                else:
                    st.error("Failed to add student. Check if Student ID already exists.")
            else:
                st.warning("Please fill in Student ID and Name.")

def view_students():
    """Displays all registered students."""
    st.subheader("Registered Students")
    query = "SELECT * FROM Student"
    df_students = execute_query(query, fetch=True)
    if df_students is not None and not df_students.empty:
        st.dataframe(df_students, use_container_width=True)
    else:
        st.info("No students registered yet.")

def add_admin_form():
    """Form to add a new admin."""
    st.subheader("Register New Administrator")
    with st.form("add_admin_form"):
        username = st.text_input("Admin Username (Unique)")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Register Admin")

        if submitted:
            if username and password:
                # Note: For a production app, the password should be securely hashed (e.g., using bcrypt).
                # This example uses plain text for simplicity, matching the existing admin_login logic.
                query = "INSERT INTO Admin (username, password) VALUES (%s, %s)"
                params = (username, password)
                
                # We commit here since we are inserting a new user
                if execute_query(query, params, commit=True) is not None:
                    st.success(f"Administrator '{username}' registered successfully.")
                else:
                    st.error("Failed to register administrator. Check if Username already exists.")
            else:
                st.warning("Please fill in both Username and Password.")


def issue_book_form():
    """Form to issue a book to a student."""
    st.subheader("Issue Book")
    with st.form("issue_book_form"):
        student_id = st.text_input("Student ID (e.g., S001)")
        book_id = st.number_input("Book ID to Issue", min_value=1, step=1)
        issue_date = date.today()
        due_date = issue_date + timedelta(days=14) # Default 14 days loan period
        st.write(f"Issue Date: **{issue_date}**")
        st.write(f"Due Date (14 days): **{due_date}**")
        submitted = st.form_submit_button("Issue Book")

        if submitted and student_id and book_id:
            # 1. Check if book exists and is available
            book_check_query = "SELECT available_copies FROM Books WHERE book_id = %s"
            df_book = execute_query(book_check_query, (book_id,), fetch=True)

            if df_book is None or df_book.empty:
                st.error("Error: Book ID not found.")
                return

            available_copies = df_book.iloc[0]['available_copies']
            if available_copies <= 0:
                st.warning("Book is currently out of stock (available copies = 0).")
                return

            # 2. Check if student exists
            student_check_query = "SELECT student_id FROM Student WHERE student_id = %s"
            df_student = execute_query(student_check_query, (student_id,), fetch=True)
            if df_student is None or df_student.empty:
                st.error("Error: Student ID not found.")
                return

            # 3. Perform Issue Transaction
            try:
                # Start transaction for atomicity
                conn = get_db_connection()
                with conn.cursor() as cursor:
                    # Issue the book
                    issue_query = """
                    INSERT INTO IssueTable (book_id, student_id, issue_date, due_date, is_returned)
                    VALUES (%s, %s, %s, %s, FALSE)
                    """
                    cursor.execute(issue_query, (book_id, student_id, issue_date, due_date))

                    # Decrease available copies
                    update_book_query = "UPDATE Books SET available_copies = available_copies - 1 WHERE book_id = %s"
                    cursor.execute(update_book_query, (book_id,))

                    conn.commit()
                    st.success(f"Book ID {book_id} issued successfully to Student ID {student_id}. Due date: {due_date}")

            except pymysql.MySQLError as e:
                st.error(f"Transaction failed (Issue Book): {e}")
                if conn: conn.rollback()
            except Exception as e:
                st.error(f"An unexpected error occurred: {e}")

def return_book_form():
    """Form to return an issued book."""
    st.subheader("Return Book")
    # Fetch all currently issued (not returned) books
    issued_query = """
    SELECT 
        it.issue_id, b.title, s.name, it.due_date, it.issue_date
    FROM IssueTable it
    JOIN Books b ON it.book_id = b.book_id
    JOIN Student s ON it.student_id = s.student_id
    WHERE it.is_returned = FALSE
    ORDER BY it.issue_date DESC
    """
    df_issued = execute_query(issued_query, fetch=True)
    
    if df_issued is not None and not df_issued.empty:
        st.info("Currently Issued Books:")
        st.dataframe(df_issued, use_container_width=True)
    else:
        st.info("No books are currently issued.")

    with st.form("return_book_form"):
        issue_id = st.number_input("Enter Issue ID to Return", min_value=1, step=1)
        return_date = date.today()
        submitted = st.form_submit_button("Process Return")

        if submitted and issue_id:
            # 1. Fetch issue details and check if already returned
            issue_info_query = "SELECT book_id, due_date, is_returned FROM IssueTable WHERE issue_id = %s"
            df_info = execute_query(issue_info_query, (issue_id,), fetch=True)

            if df_info is None or df_info.empty:
                st.error("Error: Issue ID not found.")
                return

            book_id = df_info.iloc[0]['book_id']
            due_date = df_info.iloc[0]['due_date']
            is_returned = df_info.iloc[0]['is_returned']

            if is_returned:
                st.warning(f"Issue ID {issue_id} has already been returned.")
                return

            # 2. Calculate Fine
            fine_amount = 0.00
            if return_date > due_date:
                days_overdue = (return_date - due_date).days
                # Assuming a fine of 5 INR per day
                fine_rate = 5.00
                fine_amount = days_overdue * fine_rate
                st.warning(f"Book is {days_overdue} days overdue. Fine calculated: ₹{fine_amount:.2f}")

            # 3. Perform Return Transaction
            try:
                conn = get_db_connection()
                with conn.cursor() as cursor:
                    # Update IssueTable
                    return_query = """
                    UPDATE IssueTable 
                    SET return_date = %s, is_returned = TRUE, fine_amount = %s
                    WHERE issue_id = %s
                    """
                    cursor.execute(return_query, (return_date, fine_amount, issue_id))

                    # Increase available copies
                    update_book_query = "UPDATE Books SET available_copies = available_copies + 1 WHERE book_id = %s"
                    cursor.execute(update_book_query, (book_id,))

                    conn.commit()
                    st.success(f"Book (Issue ID: {issue_id}) returned successfully.")
                    if fine_amount > 0:
                        st.success(f"Please collect fine amount: ₹{fine_amount:.2f}")
            
            except pymysql.MySQLError as e:
                st.error(f"Transaction failed (Return Book): {e}")
                if conn: conn.rollback()
            except Exception as e:
                st.error(f"An unexpected error occurred: {e}")

# --- 6. STUDENT PORTAL FUNCTIONS ---

def student_view_issued(student_id):
    """Shows books currently issued by the student."""
    st.subheader("Your Currently Issued Books")
    query = """
    SELECT 
        it.issue_id, b.title, b.author, it.issue_date, it.due_date
    FROM IssueTable it
    JOIN Books b ON it.book_id = b.book_id
    WHERE it.student_id = %s AND it.is_returned = FALSE
    ORDER BY it.due_date ASC
    """
    df_issued = execute_query(query, (student_id,), fetch=True)

    if df_issued is not None and not df_issued.empty:
        # Highlight overdue books
        today = date.today()
        df_issued['Status'] = df_issued.apply(
            lambda row: 'OVERDUE' if row['due_date'] < today else 'Active',axis=1
        )
        st.dataframe(df_issued, use_container_width=True)
    else:
        st.info("You currently have no books issued.")

def student_view_available():
    """Shows all available books."""
    st.subheader("Browse Available Books")
    search_query = st.text_input("Search by Title or Author:", key="student_book_search")

    query = """
    SELECT 
        book_id, title, author, genre, available_copies 
    FROM Books 
    WHERE available_copies > 0 AND (title LIKE %s OR author LIKE %s)
    """
    params = (f"%{search_query}%", f"%{search_query}%")
    df_books = execute_query(query, params, fetch=True)

    if df_books is not None and not df_books.empty:
        st.dataframe(df_books, use_container_width=True)
    else:
        st.info("No available books matching your search.")

# --- 7. MAIN STREAMLIT APP LAYOUT ---

def admin_portal():
    """Main layout for the Admin Portal."""
    st.title("📚 Library Admin Portal")

    # Use Streamlit Tabs for better navigation within the portal
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Dashboard", 
        "📘 Books", 
        "🧑‍🎓 Students", 
        "🔄 Issue/Return",
        "⚙️ User Management"  # Added new tab
    ])

    with tab1:
        st.header("System Overview")
        col1, col2, col3 = st.columns(3)
        
        # Total Books
        total_books = execute_query("SELECT SUM(total_copies) as total FROM Books", fetch=True)
        col1.metric("Total Books", total_books.iloc[0]['total'] if total_books is not None and total_books.iloc[0]['total'] else 0)

        # Available Books
        available_books = execute_query("SELECT SUM(available_copies) as available FROM Books", fetch=True)
        col2.metric("Available Copies", available_books.iloc[0]['available'] if available_books is not None and available_books.iloc[0]['available'] else 0)

        # Books Currently Issued
        issued_count = execute_query("SELECT COUNT(*) as issued FROM IssueTable WHERE is_returned = FALSE", fetch=True)
        col3.metric("Currently Issued", issued_count.iloc[0]['issued'] if issued_count is not None and issued_count.iloc[0]['issued'] else 0)
        
        st.subheader("Recently Issued Transactions")
        df_recent = execute_query("""
            SELECT 
                it.issue_id, b.title, s.name as student_name, it.issue_date, it.due_date
            FROM IssueTable it
            JOIN Books b ON it.book_id = b.book_id
            JOIN Student s ON it.student_id = s.student_id
            WHERE it.is_returned = FALSE
            ORDER BY it.issue_date DESC LIMIT 10
        """, fetch=True)

        if df_recent is not None and not df_recent.empty:
            st.dataframe(df_recent, use_container_width=True)
        else:
            st.info("No recent issues.")


    with tab2:
        st.header("Book Management")
        book_tab1, book_tab2, book_tab3 = st.tabs(["View Books", "Add Book", "Delete Book"])
        with book_tab1:
            search_term = st.text_input("Search Books by Title/Author/ISBN", key="admin_book_search")
            view_books(search_term)
        with book_tab2:
            add_book_form()
        with book_tab3:
            delete_book_form()

    with tab3:
        st.header("Student Management")
        student_tab1, student_tab2 = st.tabs(["View Students", "Add Student"])
        with student_tab1:
            view_students()
        with student_tab2:
            add_student_form()

    with tab4:
        st.header("Issue & Return Management")
        issue_tab1, issue_tab2 = st.tabs(["Issue Book", "Return Book"])
        with issue_tab1:
            issue_book_form()
        with issue_tab2:
            return_book_form()
            
    with tab5: # New User Management Tab
        st.header("User Management")
        user_tab1, = st.tabs(["Add New Admin"])
        with user_tab1:
            add_admin_form()


def student_portal():
    """Main layout for the Student Portal."""
    # Ensure a value exists before accessing iloc[0]
    student_info = execute_query("SELECT name FROM Student WHERE student_id = %s", (st.session_state['user_id'],), fetch=True)
    student_name = student_info.iloc[0]['name'] if student_info is not None and not student_info.empty else "Student"
    st.title(f"👋 Welcome, {student_name}!")
    st.image("system.png", use_container_width=200)
    st.caption(f"Student ID: **{st.session_state['user_id']}**")

    tab1, tab2 = st.tabs(["📚 Browse Available Books", "📖 My Issued Books"])

    with tab1:
        student_view_available()

    with tab2:
        student_view_issued(st.session_state['user_id'])


def login_screen():
    """Initial login screen to choose role."""
    
    # --- Main Content Area (Welcome) ---
    st.title("Welcome Our Library Management System")
    st.image("front.jpg", use_container_width=100)
    st.markdown("### Access your Book Inventory and Student Records")
    st.markdown("---")
    
    st.info("Please use the sidebar on the left to select your login role.")

    # --- Sidebar Login Options ---
    with st.sidebar:
        st.subheader("Login Options",)
        
        # Use radio buttons to select the login mode
        login_mode = st.radio("Select your role:", ["Admin", "Student"])
        
        

        if login_mode == "Admin":
            st.subheader("🔑 Admin Login")
            st.image("admin.png", use_container_width=True) 
            with st.form("admin_login_form"):
                admin_user = st.text_input("Username", key="al_user")
                admin_pass = st.text_input("Password", type="password", key="al_pass")
                if st.form_submit_button("Login as Admin"):
                    
                    admin_login(admin_user, admin_pass)

        elif login_mode == "Student":
            st.subheader("🧑‍🎓 Student Login")
            st.image("student.jpg", use_container_width=True)
            with st.form("student_login_form"):
                student_id = st.text_input("Student ID (e.g., S001)", key="sl_id")
                if st.form_submit_button("Login as Student"):
                    # Assuming student_login() is defined elsewhere in the main script
                    # This function call remains the same
                    student_login(student_id)

    
  

# --- MAIN APP EXECUTION ---

def main():
    """Main function to run the Streamlit app."""
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
        login_screen()
    elif st.session_state['user_role'] == 'admin':
        admin_portal()
    elif st.session_state['user_role'] == 'student':
        student_portal()

if __name__ == '__main__':
    main()

