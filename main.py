import sys
import os
import sqlite3
import json
import csv
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QLabel, QLineEdit, QPushButton,
    QVBoxLayout, QWidget, QTextEdit, QMessageBox, QComboBox,
    QStackedWidget, QDateEdit, QGridLayout, QGroupBox, QTableWidget,
    QTableWidgetItem, QAbstractItemView, QHBoxLayout, QDialog, QTabWidget,
    QDialogButtonBox, QFormLayout, QCheckBox, QScrollArea, QHBoxLayout, 
    QSpacerItem, QSizePolicy, QFileDialog, QListWidget 
)

from PyQt5.QtCore import QTime, QDate

# Default IRS Schedule C categories for both income and expense types
DEFAULT_SCHEDULE_C_CATEGORIES = {
    "income": ["Sales", "Service Income", "Interest Income"],
    "expense": [
        "Advertising", "Car and Truck Expenses", "Commissions and Fees",
        "Contract Labor", "Depletion", "Depreciation", "Employee Benefit Programs",
        "Insurance", "Interest", "Legal and Professional Services",
        "Office Expenses", "Rent or Lease", "Repairs and Maintenance",
        "Supplies", "Taxes and Licenses", "Travel", "Utilities", "Wages"
    ]
}

class IncomeExpenseDB:
    """Handles SQLite database connection and operations."""

    def __init__(self):
        try:
            self.connection = sqlite3.connect("income_expense.db")
            self.cursor = self.connection.cursor()
            self.create_tables()
        except sqlite3.Error as e:
            QMessageBox.critical(None, "Database Error", f"Error initializing database: {e}")
            sys.exit(1)

    def create_tables(self):
        """Create tables if they don't exist."""
        try:
            # Create income, expense, categories, users, customers, and employees tables
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS income (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    amount REAL NOT NULL,
                    type TEXT NOT NULL,
                    date TEXT NOT NULL,
                    comments TEXT
                )
            """)
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS expense (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    amount REAL NOT NULL,
                    type TEXT NOT NULL,
                    date TEXT NOT NULL,
                    comments TEXT
                )
            """)
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type TEXT NOT NULL,
                    category TEXT NOT NULL
                )
            """)
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL
                )
            """)
            # Include the 'data' column for customers and employees
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS customers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    data TEXT NOT NULL
                )
            """)

            # Add this for expense_files table
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS expense_files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    expense_id INTEGER NOT NULL,
                    file_path TEXT NOT NULL,
                    file_name TEXT NOT NULL,
                    FOREIGN KEY(expense_id) REFERENCES expense(id) ON DELETE CASCADE
                )
            """)

            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS employees (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    data TEXT NOT NULL
                )
            """)

            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS child_attendance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    child_id INTEGER NOT NULL,
                    date TEXT NOT NULL,
                    check_in_time TEXT,
                    check_out_time TEXT,
                    FOREIGN KEY(child_id) REFERENCES customers(id)
                )
            """)

            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS employee_attendance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    employee_id INTEGER NOT NULL,
                    date TEXT NOT NULL,
                    clock_in_time TEXT,
                    clock_out_time TEXT,
                    FOREIGN KEY(employee_id) REFERENCES employees(id)
                )
            """)

            self.connection.commit()

            # Add a default user if no user exists
            self.cursor.execute("SELECT COUNT(*) FROM users")
            if self.cursor.fetchone()[0] == 0:
                self.cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", ("admin", "password"))
                self.connection.commit()
        except sqlite3.Error as e:
            QMessageBox.critical(None, "Database Error", f"Error creating tables: {e}")

    def check_in_child(self, child_id):
        """Record check-in time for a child."""
        date = QDate.currentDate().toString("yyyy-MM-dd")
        time = QTime.currentTime().toString("HH:mm:ss")
        try:
            # Check if an attendance record exists for today
            self.cursor.execute(
                "SELECT id FROM child_attendance WHERE child_id = ? AND date = ?", (child_id, date))
            record = self.cursor.fetchone()
            if record:
                attendance_id = record[0]
                self.cursor.execute(
                    "UPDATE child_attendance SET check_in_time = ? WHERE id = ?", (time, attendance_id))
            else:
                self.cursor.execute(
                    "INSERT INTO child_attendance (child_id, date, check_in_time) VALUES (?, ?, ?)",
                    (child_id, date, time))
            self.connection.commit()
        except sqlite3.Error as e:
            QMessageBox.critical(None, "Database Error", f"Error checking in child: {e}")

    def check_out_child(self, child_id):
        """Record check-out time for a child."""
        date = QDate.currentDate().toString("yyyy-MM-dd")
        time = QTime.currentTime().toString("HH:mm:ss")
        try:
            self.cursor.execute(
                "SELECT id FROM child_attendance WHERE child_id = ? AND date = ?", (child_id, date))
            record = self.cursor.fetchone()
            if record:
                attendance_id = record[0]
                self.cursor.execute(
                    "UPDATE child_attendance SET check_out_time = ? WHERE id = ?", (time, attendance_id))
                self.connection.commit()
            else:
                QMessageBox.warning(None, "Attendance Error", "Child has not been checked in today.")
        except sqlite3.Error as e:
            QMessageBox.critical(None, "Database Error", f"Error checking out child: {e}")

    def get_child_attendance(self, child_id, date):
        """Get attendance record for a child on a specific date."""
        try:
            self.cursor.execute(
                "SELECT check_in_time, check_out_time FROM child_attendance WHERE child_id = ? AND date = ?",
                (child_id, date))
            result = self.cursor.fetchone()
            if result:
                return {'check_in_time': result[0], 'check_out_time': result[1]}
            else:
                return None
        except sqlite3.Error as e:
            QMessageBox.critical(None, "Database Error", f"Error retrieving attendance: {e}")
            return None

    def validate_user(self, username, password):
        """Validate user credentials."""
        try:
            self.cursor.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
            return self.cursor.fetchone() is not None
        except sqlite3.Error as e:
            QMessageBox.critical(None, "Database Error", f"Error validating user: {e}")
            return False

    def add_income(self, amount, income_type, date, comments):
        """Add a new income record."""
        try:
            self.cursor.execute("INSERT INTO income (amount, type, date, comments) VALUES (?, ?, ?, ?)",
                                (amount, income_type, date, comments))
            self.connection.commit()
        except sqlite3.Error as e:
            QMessageBox.critical(None, "Database Error", f"Error adding income: {e}")

    def get_income(self):
        """Retrieve all income records."""
        try:
            query = "SELECT * FROM income"
            self.cursor.execute(query)
            return self.cursor.fetchall()
        except sqlite3.Error as e:
            QMessageBox.critical(None, "Database Error", f"Error retrieving income: {e}")
            return []

    def update_income(self, income_id, amount, income_type, date, comments):
        """Update an existing income record."""
        try:
            self.cursor.execute("UPDATE income SET amount = ?, type = ?, date = ?, comments = ? WHERE id = ?",
                                (amount, income_type, date, comments, income_id))
            self.connection.commit()
        except sqlite3.Error as e:
            QMessageBox.critical(None, "Database Error", f"Error updating income: {e}")

    def delete_income(self, income_id):
        """Delete an income record."""
        try:
            self.cursor.execute("DELETE FROM income WHERE id = ?", (income_id,))
            self.connection.commit()
        except sqlite3.Error as e:
            QMessageBox.critical(None, "Database Error", f"Error deleting income: {e}")

    def add_expense(self, amount, expense_type, date, comments, files=None):
        """Add a new expense record with optional files."""
        try:
            self.cursor.execute(
                "INSERT INTO expense (amount, type, date, comments) VALUES (?, ?, ?, ?)",
                (amount, expense_type, date, comments))
            expense_id = self.cursor.lastrowid

            # Save attached files
            if files:
                for file_path in files:
                    self.save_expense_file(expense_id, file_path)

            self.connection.commit()
        except sqlite3.Error as e:
            QMessageBox.critical(None, "Database Error", f"Error adding expense: {e}")

    def save_expense_file(self, expense_id, file_path):
        """Save an expense file to the filesystem and record in the database."""
        try:
            # Create a directory for expense files if it doesn't exist
            os.makedirs('expense_files', exist_ok=True)

            # Generate a unique filename
            base_name = os.path.basename(file_path)
            unique_name = f"{expense_id}_{base_name}"
            dest_path = os.path.join('expense_files', unique_name)

            # Copy the file to the destination
            import shutil
            shutil.copy(file_path, dest_path)

            # Save file info to the database
            self.cursor.execute(
                "INSERT INTO expense_files (expense_id, file_path, file_name) VALUES (?, ?, ?)",
                (expense_id, dest_path, base_name))
        except Exception as e:
            QMessageBox.critical(None, "File Error", f"Error saving file: {e}")

    def get_expense_files(self, expense_id):
        """Retrieve files attached to an expense."""
        try:
            self.cursor.execute(
                "SELECT file_path, file_name FROM expense_files WHERE expense_id = ?", (expense_id,))
            files = [{'file_path': row[0], 'file_name': row[1]} for row in self.cursor.fetchall()]
            return files
        except sqlite3.Error as e:
            QMessageBox.critical(None, "Database Error", f"Error retrieving files: {e}")
            return []

    def get_expenses(self):
        """Retrieve all expense records."""
        try:
            query = "SELECT * FROM expense"
            self.cursor.execute(query)
            return self.cursor.fetchall()
        except sqlite3.Error as e:
            QMessageBox.critical(None, "Database Error", f"Error retrieving expenses: {e}")
            return []

    def update_expense(self, expense_id, amount, expense_type, date, comments):
        """Update an existing expense record."""
        try:
            self.cursor.execute("UPDATE expense SET amount = ?, type = ?, date = ?, comments = ? WHERE id = ?",
                                (amount, expense_type, date, comments, expense_id))
            self.connection.commit()
        except sqlite3.Error as e:
            QMessageBox.critical(None, "Database Error", f"Error updating expense: {e}")

    def delete_expense(self, expense_id):
        """Delete an expense record and its associated files."""
        try:
            # Retrieve file paths to delete them from the filesystem
            files = self.get_expense_files(expense_id)
            for file in files:
                if os.path.exists(file['file_path']):
                    os.remove(file['file_path'])

            # Delete expense files from the database
            self.cursor.execute("DELETE FROM expense_files WHERE expense_id = ?", (expense_id,))
            # Delete the expense record
            self.cursor.execute("DELETE FROM expense WHERE id = ?", (expense_id,))
            self.connection.commit()
        except sqlite3.Error as e:
            QMessageBox.critical(None, "Database Error", f"Error deleting expense: {e}")

    def add_customer(self, customer_data):
        """Add a new customer."""
        try:
            data_json = json.dumps(customer_data)
            self.cursor.execute("INSERT INTO customers (data) VALUES (?)", (data_json,))
            self.connection.commit()
        except sqlite3.Error as e:
            QMessageBox.critical(None, "Database Error", f"Error adding customer: {e}")

    def get_customers(self):
        """Retrieve all customers."""
        try:
            self.cursor.execute("SELECT id, data FROM customers")
            customers = []
            for row in self.cursor.fetchall():
                customer_id = row[0]
                customer_data = json.loads(row[1])
                customer_data['id'] = customer_id
                customers.append(customer_data)
            return customers
        except sqlite3.Error as e:
            QMessageBox.critical(None, "Database Error", f"Error retrieving customers: {e}")
            return []

    def update_customer(self, customer_id, customer_data):
        """Update an existing customer."""
        try:
            data_json = json.dumps(customer_data)
            self.cursor.execute("UPDATE customers SET data = ? WHERE id = ?",
                                (data_json, customer_id))
            self.connection.commit()
        except sqlite3.Error as e:
            QMessageBox.critical(None, "Database Error", f"Error updating customer: {e}")

    def delete_customer(self, customer_id):
        """Delete a customer."""
        try:
            self.cursor.execute("DELETE FROM customers WHERE id = ?", (customer_id,))
            self.connection.commit()
        except sqlite3.Error as e:
            QMessageBox.critical(None, "Database Error", f"Error deleting customer: {e}")

    # def add_employee(self, employee_data):
    #     """Add a new employee."""
    #     try:
    #         data_json = json.dumps(employee_data)
    #         self.cursor.execute("INSERT INTO employees (data) VALUES (?)", (data_json,))
    #         self.connection.commit()
    #     except sqlite3.Error as e:
    #         QMessageBox.critical(None, "Database Error", f"Error adding employee: {e}")
    
    class IncomeExpenseDB:
        def add_employee(self, employee_data):
            """Add a new employee with comprehensive details."""
            try:
                # Example: you can serialize the employee data as JSON if needed, or handle fields individually
                data_json = json.dumps(employee_data)
                self.cursor.execute(
                    "INSERT INTO employees (data) VALUES (?)", (data_json,))
                self.connection.commit()
            except sqlite3.Error as e:
                QMessageBox.critical(None, "Database Error", f"Error adding employee: {e}")



    def get_employees(self):
        """Retrieve all employees."""
        try:
            self.cursor.execute("SELECT id, data FROM employees")
            employees = []
            for row in self.cursor.fetchall():
                employee_id = row[0]
                employee_data = json.loads(row[1])
                employee_data['id'] = employee_id
                employees.append(employee_data)
            return employees
        except sqlite3.Error as e:
            QMessageBox.critical(None, "Database Error", f"Error retrieving employees: {e}")
            return []

    def update_employee(self, employee_id, employee_data):
        """Update an existing employee."""
        try:
            data_json = json.dumps(employee_data)
            self.cursor.execute("UPDATE employees SET data = ? WHERE id = ?",
                                (data_json, employee_id))
            self.connection.commit()
        except sqlite3.Error as e:
            QMessageBox.critical(None, "Database Error", f"Error updating employee: {e}")

    def delete_employee(self, employee_id):
        """Delete an employee."""
        try:
            self.cursor.execute("DELETE FROM employees WHERE id = ?", (employee_id,))
            self.connection.commit()
        except sqlite3.Error as e:
            QMessageBox.critical(None, "Database Error", f"Error deleting employee: {e}")

    def add_bulk_entries(self, entries, entry_type):
        """Add multiple income or expense entries."""
        try:
            table = 'income' if entry_type == 'income' else 'expense'
            self.cursor.executemany(
                f"INSERT INTO {table} (amount, type, date, comments) VALUES (?, ?, ?, ?)",
                entries
            )
            self.connection.commit()
        except sqlite3.Error as e:
            QMessageBox.critical(None, "Database Error", f"Error adding entries: {e}")

class EmployeeAttendanceScreen(QWidget):
    """Screen for managing employee attendance."""
    def __init__(self, parent):
        super().__init__()
        self.parent = parent

        layout = QVBoxLayout()

        # Table to display employees
        self.table_widget = QTableWidget()
        self.table_widget.setColumnCount(5)
        self.table_widget.setHorizontalHeaderLabels(["Employee ID", "Name", "Clock-In", "Clock-Out", "Status"])
        layout.addWidget(self.table_widget)

        # Back button
        self.back_button = QPushButton("Back")
        self.back_button.clicked.connect(lambda: self.parent.show_screen("Main"))
        layout.addWidget(self.back_button)

        self.setLayout(layout)
        self.load_employees()

    def load_employees(self):
        employees = self.parent.db.get_employees()

        self.table_widget.setRowCount(len(employees))

        for row, employee in enumerate(employees):
            employee_id = employee['id']
            name = employee.get('name', '')

            self.table_widget.setItem(row, 0, QTableWidgetItem(str(employee_id)))
            self.table_widget.setItem(row, 1, QTableWidgetItem(name))

            # Clock-In Button
            clock_in_button = QPushButton("Clock-In")
            clock_in_button.clicked.connect(lambda _, eid=employee_id: self.clock_in_employee(eid))
            self.table_widget.setCellWidget(row, 2, clock_in_button)

            # Clock-Out Button
            clock_out_button = QPushButton("Clock-Out")
            clock_out_button.clicked.connect(lambda _, eid=employee_id: self.clock_out_employee(eid))
            self.table_widget.setCellWidget(row, 3, clock_out_button)

            # Status
            status_item = QTableWidgetItem()
            self.table_widget.setItem(row, 4, status_item)
            self.update_status(employee_id, status_item)

    def update_status(self, employee_id, status_item):
        today = QDate.currentDate().toString("yyyy-MM-dd")
        attendance = self.parent.db.get_employee_attendance(employee_id, today)
        if attendance:
            if attendance['clock_in_time'] and not attendance['clock_out_time']:
                status_item.setText("Clocked In")
            elif attendance['clock_in_time'] and attendance['clock_out_time']:
                status_item.setText("Clocked Out")
            else:
                status_item.setText("Absent")
        else:
            status_item.setText("Absent")

    def clock_in_employee(self, employee_id):
        self.parent.db.clock_in_employee(employee_id)
        self.load_employees()

    def clock_out_employee(self, employee_id):
        self.parent.db.clock_out_employee(employee_id)
        self.load_employees()

    def clock_in_employee(self, employee_id):
        """Record clock-in time for an employee."""
        date = QDate.currentDate().toString("yyyy-MM-dd")
        time = QTime.currentTime().toString("HH:mm:ss")
        try:
            # Check if an attendance record exists for today
            self.cursor.execute(
                "SELECT id FROM employee_attendance WHERE employee_id = ? AND date = ?", (employee_id, date))
            record = self.cursor.fetchone()
            if record:
                attendance_id = record[0]
                self.cursor.execute(
                    "UPDATE employee_attendance SET clock_in_time = ? WHERE id = ?", (time, attendance_id))
            else:
                self.cursor.execute(
                    "INSERT INTO employee_attendance (employee_id, date, clock_in_time) VALUES (?, ?, ?)",
                    (employee_id, date, time))
            self.connection.commit()
        except sqlite3.Error as e:
            QMessageBox.critical(None, "Database Error", f"Error clocking in employee: {e}")

    def clock_out_employee(self, employee_id):
        """Record clock-out time for an employee."""
        date = QDate.currentDate().toString("yyyy-MM-dd")
        time = QTime.currentTime().toString("HH:mm:ss")
        try:
            self.cursor.execute(
                "SELECT id FROM employee_attendance WHERE employee_id = ? AND date = ?", (employee_id, date))
            record = self.cursor.fetchone()
            if record:
                attendance_id = record[0]
                self.cursor.execute(
                    "UPDATE employee_attendance SET clock_out_time = ? WHERE id = ?", (time, attendance_id))
                self.connection.commit()
            else:
                QMessageBox.warning(None, "Attendance Error", "Employee has not clocked in today.")
        except sqlite3.Error as e:
            QMessageBox.critical(None, "Database Error", f"Error clocking out employee: {e}")

    def get_employee_attendance(self, employee_id, date):
        """Get attendance record for an employee on a specific date."""
        try:
            self.cursor.execute(
                "SELECT clock_in_time, clock_out_time FROM employee_attendance WHERE employee_id = ? AND date = ?",
                (employee_id, date))
            result = self.cursor.fetchone()
            if result:
                return {'clock_in_time': result[0], 'clock_out_time': result[1]}
            else:
                return None
        except sqlite3.Error as e:
            QMessageBox.critical(None, "Database Error", f"Error retrieving attendance: {e}")
            return None


class ChildAttendanceScreen(QWidget):
    """Screen for managing child attendance."""
    def __init__(self, parent):
        super().__init__()
        self.parent = parent

        layout = QVBoxLayout()

        # Back button at the top
        self.back_button = QPushButton("Back")
        self.back_button.setFixedSize(80, 30)  # Smaller back button at the top
        self.back_button.clicked.connect(lambda: parent.show_screen("Main"))
        layout.addWidget(self.back_button)

        # Table to display children
        self.table_widget = QTableWidget()
        self.table_widget.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_widget.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table_widget.setEditTriggers(QAbstractItemView.NoEditTriggers)
        layout.addWidget(self.table_widget)

        self.table_widget.setColumnCount(5)
        self.table_widget.setHorizontalHeaderLabels(["Child ID", "Child Name", "Check-In", "Check-Out", "Status"])

        self.load_children()

        self.setLayout(layout)

    # """Screen for managing child attendance."""
    # def __init__(self, parent):
    #     super().__init__()
    #     self.parent = parent

    #     layout = QVBoxLayout()

    #     # Table to display children
    #     self.table_widget = QTableWidget()
    #     self.table_widget.setColumnCount(5)
    #     self.table_widget.setHorizontalHeaderLabels(["Child ID", "Child Name", "Check-In", "Check-Out", "Status"])
    #     layout.addWidget(self.table_widget)

    #     # Back button
    #     self.back_button = QPushButton("Back")
    #     self.back_button.clicked.connect(lambda: self.parent.show_screen("Main"))
    #     layout.addWidget(self.back_button)

    #     self.setLayout(layout)
    #     self.load_children()

    def load_children(self):
        children = self.parent.db.get_customers()  # Assuming enrolled children are in customers
        enrolled_children = [child for child in children if child.get('enrollment_status') == 'Enrolled']

        self.table_widget.setRowCount(len(enrolled_children))

        for row, child in enumerate(enrolled_children):
            child_id = child['id']
            child_name = child.get('child_full_name', '')

            self.table_widget.setItem(row, 0, QTableWidgetItem(str(child_id)))
            self.table_widget.setItem(row, 1, QTableWidgetItem(child_name))

            # Check-In Button
            check_in_button = QPushButton("Check-In")
            check_in_button.clicked.connect(lambda _, cid=child_id: self.check_in_child(cid))
            self.table_widget.setCellWidget(row, 2, check_in_button)

            # Check-Out Button
            check_out_button = QPushButton("Check-Out")
            check_out_button.clicked.connect(lambda _, cid=child_id: self.check_out_child(cid))
            self.table_widget.setCellWidget(row, 3, check_out_button)

            # Status
            status_item = QTableWidgetItem()
            self.table_widget.setItem(row, 4, status_item)
            self.update_status(child_id, status_item)

    def update_status(self, child_id, status_item):
        today = QDate.currentDate().toString("yyyy-MM-dd")
        attendance = self.parent.db.get_child_attendance(child_id, today)
        if attendance:
            if attendance['check_in_time'] and not attendance['check_out_time']:
                status_item.setText("Checked In")
            elif attendance['check_in_time'] and attendance['check_out_time']:
                status_item.setText("Checked Out")
            else:
                status_item.setText("Absent")
        else:
            status_item.setText("Absent")

    # def load_children(self):
    #     customers = self.parent.db.get_customers()
    #     enrolled_children = [c for c in customers if c.get('enrollment_status') == 'Enrolled']

    #     self.table_widget.setRowCount(len(enrolled_children))

    #     for row, child in enumerate(enrolled_children):
    #         child_id = child['id']
    #         child_name = child.get('child_full_name', '')

    #         self.table_widget.setItem(row, 0, QTableWidgetItem(str(child_id)))
    #         self.table_widget.setItem(row, 1, QTableWidgetItem(child_name))

    #         # Check-In Button
    #         check_in_button = QPushButton("Check-In")
    #         check_in_button.clicked.connect(lambda _, cid=child_id: self.check_in_child(cid))
    #         self.table_widget.setCellWidget(row, 2, check_in_button)

    #         # Check-Out Button
    #         check_out_button = QPushButton("Check-Out")
    #         check_out_button.clicked.connect(lambda _, cid=child_id: self.check_out_child(cid))
    #         self.table_widget.setCellWidget(row, 3, check_out_button)

    #         # Status
    #         status_item = QTableWidgetItem()
    #         self.table_widget.setItem(row, 4, status_item)
    #         self.update_status(child_id, status_item)

    # def update_status(self, child_id, status_item):
    #     today = QDate.currentDate().toString("yyyy-MM-dd")
    #     attendance = self.parent.db.get_child_attendance(child_id, today)
    #     if attendance:
    #         if attendance['check_in_time'] and not attendance['check_out_time']:
    #             status_item.setText("Checked In")
    #         elif attendance['check_in_time'] and attendance['check_out_time']:
    #             status_item.setText("Checked Out")
    #         else:
    #             status_item.setText("Absent")
    #     else:
    #         status_item.setText("Absent")

    def check_in_child(self, child_id):
        date = QDate.currentDate().toString("yyyy-MM-dd")
        time = QTime.currentTime().toString("HH:mm:ss")
        try:
            # Check if an attendance record already exists for today
            self.parent.db.check_in_child(child_id, date, time)
            QMessageBox.information(self, "Check-In Successful", f"Child ID {child_id} has been checked in.")
            self.load_children()
        except Exception as e:
            QMessageBox.critical(self, "Check-In Error", str(e))

    def check_out_child(self, child_id):
        date = QDate.currentDate().toString("yyyy-MM-dd")
        time = QTime.currentTime().toString("HH:mm:ss")
        try:
            self.parent.db.check_out_child(child_id, date, time)
            QMessageBox.information(self, "Check-Out Successful", f"Child ID {child_id} has been checked out.")
            self.load_children()
        except Exception as e:
            QMessageBox.critical(self, "Check-Out Error", str(e))

    # def check_in_child(self, child_id):
    #     self.parent.db.check_in_child(child_id)
    #     self.load_children()

    # def check_out_child(self, child_id):
    #     self.parent.db.check_out_child(child_id)
    #     self.load_children()

class LoginScreen(QWidget):
    """Screen for logging into the application."""
    def __init__(self, parent):
        super().__init__()
        self.parent = parent

        # Main layout
        main_layout = QVBoxLayout()

        # Spacer at the top
        main_layout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))

        # Center layout for form
        center_layout = QVBoxLayout()

        self.username_label = QLabel("Username:")
        center_layout.addWidget(self.username_label)
        self.username_input = QLineEdit()
        center_layout.addWidget(self.username_input)

        self.password_label = QLabel("Password:")
        center_layout.addWidget(self.password_label)
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        center_layout.addWidget(self.password_input)

        self.login_button = QPushButton("Login")
        self.login_button.clicked.connect(self.handle_login)
        center_layout.addWidget(self.login_button)

        # Center layout in the middle
        main_layout.addLayout(center_layout)

        # Spacer at the bottom
        main_layout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))

        # Center horizontally
        h_layout = QHBoxLayout()
        h_layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        h_layout.addLayout(main_layout)
        h_layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        self.setLayout(h_layout)

    def handle_login(self):
        username = self.username_input.text()
        password = self.password_input.text()
        if self.parent.db.validate_user(username, password):
            self.parent.show_screen("Main")
        else:
            QMessageBox.warning(self, "Login Failed", "Invalid username or password.")

class MainScreen(QWidget):
    """Main screen for navigating between different features."""
    def __init__(self, parent):
        super().__init__()
        self.parent = parent

        # Main layout
        main_layout = QVBoxLayout()

        # Spacer at the top
        main_layout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))

        # Center layout for groups
        center_layout = QVBoxLayout()

        # Group for Income and Expenses
        income_expense_group = QGroupBox("Income and Expenses")
        ie_layout = QVBoxLayout()
        ie_layout.addWidget(self.create_button("Manage Income", "ManageIncome"))
        ie_layout.addWidget(self.create_button("Manage Expenses", "ManageExpense"))
        income_expense_group.setLayout(ie_layout)
        center_layout.addWidget(income_expense_group)

        # Group for Management
        management_group = QGroupBox("Management")
        management_layout = QVBoxLayout()
        management_layout.addWidget(self.create_button("Manage Customers", "ManageCustomers"))
        management_layout.addWidget(self.create_button("Manage Employees", "ManageEmployees"))
        management_group.setLayout(management_layout)
        center_layout.addWidget(management_group)

        # Group for Reports
        reports_group = QGroupBox("Reports")
        reports_layout = QVBoxLayout()
        reports_layout.addWidget(self.create_button("Profit and Loss Report", "ProfitLoss"))
        reports_layout.addWidget(self.create_button("Balance Sheet Report", "BalanceSheet"))
        reports_layout.addWidget(self.create_button("Cash Flow Statement", "CashFlow"))
        reports_layout.addWidget(self.create_button("Tax Summary Report", "TaxSummary"))
        reports_group.setLayout(reports_layout)
        center_layout.addWidget(reports_group)

        self.attendance_button = QPushButton("Child Attendance")
        self.attendance_button.clicked.connect(lambda: parent.show_screen("ChildAttendance"))
        center_layout.addWidget(self.attendance_button)

        self.employee_attendance_button = QPushButton("Employee Attendance")
        self.employee_attendance_button.clicked.connect(lambda: parent.show_screen("EmployeeAttendance"))
        center_layout.addWidget(self.employee_attendance_button)

        main_layout.addLayout(center_layout)

        # Spacer at the bottom
        main_layout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))

        # Center horizontally
        h_layout = QHBoxLayout()
        h_layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        h_layout.addLayout(main_layout)
        h_layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        self.setLayout(h_layout)

    def create_button(self, text, screen_name):
        button = QPushButton(text)
        button.clicked.connect(lambda: self.parent.show_screen(screen_name))
        return button

class BulkUploadDialog(QDialog):
    """Dialog for bulk uploading income or expense entries."""
    def __init__(self, parent, title, entry_type):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.entry_type = entry_type  # 'income' or 'expense'
        self.parent = parent

        layout = QVBoxLayout()

        instructions = QLabel("Select a CSV file with the following columns:\n"
                              "Amount, Type, Date (YYYY-MM-DD), Comments")
        layout.addWidget(instructions)

        self.select_file_button = QPushButton("Select CSV File")
        self.select_file_button.clicked.connect(self.select_file)
        layout.addWidget(self.select_file_button)

        self.status_text = QTextEdit()
        self.status_text.setReadOnly(True)
        layout.addWidget(self.status_text)

        # Buttons
        self.button_box = QDialogButtonBox(QDialogButtonBox.Close)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        self.setLayout(layout)

    def select_file(self):
        options = QFileDialog.Options()
        filename, _ = QFileDialog.getOpenFileName(self, "Select CSV File", "", "CSV Files (*.csv)", options=options)
        if filename:
            self.process_csv(filename)

    def process_csv(self, filename):
        success_count = 0
        error_count = 0
        errors = []

        with open(filename, newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            required_fields = {'Amount', 'Type', 'Date', 'Comments'}

            if not required_fields.issubset(reader.fieldnames):
                QMessageBox.warning(self, "CSV Error", f"CSV file must contain columns: {', '.join(required_fields)}")
                return

            for idx, row in enumerate(reader, start=1):
                try:
                    amount = float(row['Amount'])
                    entry_type = row['Type']
                    date = row['Date']
                    comments = row['Comments']

                    if self.entry_type == 'income':
                        self.parent.db.add_income(amount, entry_type, date, comments)
                    else:
                        self.parent.db.add_expense(amount, entry_type, date, comments)
                    success_count += 1
                except Exception as e:
                    error_count += 1
                    errors.append(f"Row {idx}: {e}")

        status_message = f"Bulk Upload Completed:\nSuccess: {success_count}\nErrors: {error_count}"
        if errors:
            status_message += "\n\nError Details:\n" + "\n".join(errors)
        self.status_text.setText(status_message)

class IncomeExpenseApp(QMainWindow):
    """Main application window with stacked widgets for different screens."""
    def __init__(self):
        super().__init__()

        # Window setup
        self.setWindowTitle("Income and Expense Manager")
        self.setGeometry(100, 100, 800, 600)

        # Initialize the SQLite database
        self.db = IncomeExpenseDB()

        # Create a stacked widget to switch between screens
        self.stack = QStackedWidget()

        # Create instances of each screen
        self.login_screen = LoginScreen(self)
        self.main_screen = MainScreen(self)
        self.manage_income_screen = ManageIncomeScreen(self)
        self.manage_expense_screen = ManageExpenseScreen(self)
        self.manage_customers_screen = ManageCustomersScreen(self)
        self.manage_employees_screen = ManageEmployeesScreen(self)
        self.profit_loss_screen = ProfitLossScreen(self)
        self.balance_sheet_screen = BalanceSheetScreen(self)
        self.cash_flow_screen = CashFlowScreen(self)
        self.tax_summary_screen = TaxSummaryScreen(self)
        self.child_attendance_screen = ChildAttendanceScreen(self)
        self.employee_attendance_screen = EmployeeAttendanceScreen(self)

        # Add all screens to the stacked widget
        self.stack.addWidget(self.login_screen)
        self.stack.addWidget(self.main_screen)
        self.stack.addWidget(self.manage_income_screen)
        self.stack.addWidget(self.manage_expense_screen)
        self.stack.addWidget(self.manage_customers_screen)
        self.stack.addWidget(self.manage_employees_screen)
        self.stack.addWidget(self.profit_loss_screen)
        self.stack.addWidget(self.balance_sheet_screen)
        self.stack.addWidget(self.cash_flow_screen)
        self.stack.addWidget(self.tax_summary_screen)
        self.stack.addWidget(self.child_attendance_screen)
        self.stack.addWidget(self.employee_attendance_screen)

        # Set main widget to the stacked widget
        self.setCentralWidget(self.stack)
        self.show_screen("Login")

    def show_screen(self, screen_name):
        """Switch between screens."""
        screen_mapping = {
            "Login": self.login_screen,
            "Main": self.main_screen,
            "ManageIncome": self.manage_income_screen,
            "ManageExpense": self.manage_expense_screen,
            "ManageCustomers": self.manage_customers_screen,
            "ManageEmployees": self.manage_employees_screen,
            "ProfitLoss": self.profit_loss_screen,
            "BalanceSheet": self.balance_sheet_screen,
            "CashFlow": self.cash_flow_screen,
            "TaxSummary": self.tax_summary_screen,
            "ChildAttendance": self.child_attendance_screen,
            "EmployeeAttendance": self.employee_attendance_screen
        }

        if screen_name in screen_mapping:
            self.stack.setCurrentWidget(screen_mapping[screen_name])
        else:
            QMessageBox.critical(self, "Navigation Error", f"Screen '{screen_name}' not found.")

class ManageIncomeScreen(QWidget):
    """Screen for managing income entries."""
    def __init__(self, parent):
        super().__init__()
        self.parent = parent

        layout = QVBoxLayout()

        # Table to display income entries
        self.table_widget = QTableWidget()
        self.table_widget.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_widget.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_widget.setSelectionMode(QAbstractItemView.SingleSelection)
        layout.addWidget(self.table_widget)

        # Buttons for operations
        self.add_button = QPushButton("Add Income")
        self.add_button.clicked.connect(self.add_income)
        layout.addWidget(self.add_button)

        self.edit_button = QPushButton("Edit Income")
        self.edit_button.clicked.connect(self.edit_income)
        layout.addWidget(self.edit_button)

        self.delete_button = QPushButton("Delete Income")
        self.delete_button.clicked.connect(self.delete_income)
        layout.addWidget(self.delete_button)

        # Add Bulk Upload button
        self.bulk_upload_button = QPushButton("Bulk Upload Income")
        self.bulk_upload_button.clicked.connect(self.bulk_upload_income)
        layout.addWidget(self.bulk_upload_button)

        # Back button
        self.back_button = QPushButton("Back")
        self.back_button.clicked.connect(lambda: self.parent.show_screen("Main"))
        layout.addWidget(self.back_button)

        self.setLayout(layout)
        self.load_income()

    def load_income(self):
        income_entries = self.parent.db.get_income()
        self.table_widget.setRowCount(len(income_entries))
        self.table_widget.setColumnCount(5)
        self.table_widget.setHorizontalHeaderLabels(["ID", "Amount", "Type", "Date", "Comments"])
        for row, entry in enumerate(income_entries):
            for col, value in enumerate(entry):
                self.table_widget.setItem(row, col, QTableWidgetItem(str(value)))

    def add_income(self):
        dialog = IncomeDialog(self.parent, "Add Income")
        if dialog.exec_():
            data = dialog.get_data()
            self.parent.db.add_income(data['amount'], data['type'], data['date'], data['comments'])
            self.load_income()

    def edit_income(self):
        selected_items = self.table_widget.selectedItems()
        if selected_items:
            income_id = int(selected_items[0].text())
            amount = selected_items[1].text()
            income_type = selected_items[2].text()
            date = selected_items[3].text()
            comments = selected_items[4].text()

            dialog = IncomeDialog(self.parent, "Edit Income", {
                'amount': amount,
                'type': income_type,
                'date': date,
                'comments': comments
            })
            if dialog.exec_():
                data = dialog.get_data()
                self.parent.db.update_income(income_id, data['amount'], data['type'], data['date'], data['comments'])
                self.load_income()
        else:
            QMessageBox.warning(self, "Selection Error", "Please select an income entry to edit.")

    def delete_income(self):
        selected_items = self.table_widget.selectedItems()
        if selected_items:
            income_id = int(selected_items[0].text())
            reply = QMessageBox.question(self, "Delete Income", "Are you sure you want to delete this income entry?",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.parent.db.delete_income(income_id)
                self.load_income()
        else:
            QMessageBox.warning(self, "Selection Error", "Please select an income entry to delete.")

    def bulk_upload_income(self):
        dialog = BulkUploadDialog(self.parent, "Bulk Upload Income", "income")
        dialog.exec_()
        self.load_income()

class IncomeDialog(QDialog):
    """Dialog for adding/editing income entries."""
    def __init__(self, parent, title, income_data=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.income_data = income_data

        layout = QFormLayout()

        self.amount_input = QLineEdit()
        self.type_combobox = QComboBox()
        self.type_combobox.addItems(DEFAULT_SCHEDULE_C_CATEGORIES["income"])
        self.date_input = QDateEdit()
        self.date_input.setCalendarPopup(True)
        self.date_input.setDate(QDate.currentDate())
        self.comments_input = QTextEdit()

        layout.addRow("Amount:", self.amount_input)
        layout.addRow("Type:", self.type_combobox)
        layout.addRow("Date:", self.date_input)
        layout.addRow("Comments:", self.comments_input)

        # Buttons
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.validate_and_accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        self.setLayout(layout)

        # Load data if editing existing income
        if self.income_data:
            self.load_income_data()

    def load_income_data(self):
        data = self.income_data
        self.amount_input.setText(str(data['amount']))
        self.type_combobox.setCurrentText(data['type'])
        self.date_input.setDate(QDate.fromString(data['date'], "yyyy-MM-dd"))
        self.comments_input.setPlainText(data['comments'])

    def validate_and_accept(self):
        if self.amount_input.text() == '':
            QMessageBox.warning(self, "Input Error", "Amount is required.")
            return
        self.accept()

    def get_data(self):
        data = {
            'amount': float(self.amount_input.text()),
            'type': self.type_combobox.currentText(),
            'date': self.date_input.date().toString("yyyy-MM-dd"),
            'comments': self.comments_input.toPlainText()
        }
        return data

class ManageExpenseScreen(QWidget):
    """Screen for managing expense entries."""
    def __init__(self, parent):
        super().__init__()
        self.parent = parent

        layout = QVBoxLayout()

        # Table to display expense entries
        self.table_widget = QTableWidget()
        self.table_widget.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_widget.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_widget.setSelectionMode(QAbstractItemView.SingleSelection)
        layout.addWidget(self.table_widget)

        # Buttons for operations
        self.add_button = QPushButton("Add Expense")
        self.add_button.clicked.connect(self.add_expense)
        layout.addWidget(self.add_button)

        self.edit_button = QPushButton("Edit Expense")
        self.edit_button.clicked.connect(self.edit_expense)
        layout.addWidget(self.edit_button)

        self.delete_button = QPushButton("Delete Expense")
        self.delete_button.clicked.connect(self.delete_expense)
        layout.addWidget(self.delete_button)

        # Add Bulk Upload button
        self.bulk_upload_button = QPushButton("Bulk Upload Expenses")
        self.bulk_upload_button.clicked.connect(self.bulk_upload_expense)
        layout.addWidget(self.bulk_upload_button)

        # Back button
        self.back_button = QPushButton("Back")
        self.back_button.clicked.connect(lambda: self.parent.show_screen("Main"))
        layout.addWidget(self.back_button)

        self.setLayout(layout)
        self.load_expenses()

    def load_expenses(self):
        expense_entries = self.parent.db.get_expenses()
        self.table_widget.setRowCount(len(expense_entries))
        self.table_widget.setColumnCount(5)
        self.table_widget.setHorizontalHeaderLabels(["ID", "Amount", "Type", "Date", "Comments"])
        for row, entry in enumerate(expense_entries):
            for col, value in enumerate(entry):
                self.table_widget.setItem(row, col, QTableWidgetItem(str(value)))

    def add_expense(self):
        dialog = ExpenseDialog(self.parent, "Add Expense")
        if dialog.exec_():
            data = dialog.get_data()
            self.parent.db.add_expense(data['amount'], data['type'], data['date'], data['comments'])
            self.load_expenses()

    def edit_expense(self):
        selected_items = self.table_widget.selectedItems()
        if selected_items:
            expense_id = int(selected_items[0].text())
            amount = selected_items[1].text()
            expense_type = selected_items[2].text()
            date = selected_items[3].text()
            comments = selected_items[4].text()

            dialog = ExpenseDialog(self.parent, "Edit Expense", {
                'amount': amount,
                'type': expense_type,
                'date': date,
                'comments': comments
            })
            if dialog.exec_():
                data = dialog.get_data()
                self.parent.db.update_expense(expense_id, data['amount'], data['type'], data['date'], data['comments'])
                self.load_expenses()
        else:
            QMessageBox.warning(self, "Selection Error", "Please select an expense entry to edit.")

    def delete_expense(self):
        selected_items = self.table_widget.selectedItems()
        if selected_items:
            expense_id = int(selected_items[0].text())
            reply = QMessageBox.question(self, "Delete Expense", "Are you sure you want to delete this expense entry?",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.parent.db.delete_expense(expense_id)
                self.load_expenses()
        else:
            QMessageBox.warning(self, "Selection Error", "Please select an expense entry to delete.")

    def bulk_upload_expense(self):
        dialog = BulkUploadDialog(self.parent, "Bulk Upload Expenses", "expense")
        dialog.exec_()
        self.load_expenses()

class ExpenseDialog(QDialog):
    """Dialog for adding/editing expense entries."""
    def __init__(self, parent, title, expense_data=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.expense_data = expense_data
        self.files = []  # List to store file paths
        self.parent = parent

        layout = QVBoxLayout()
        form_layout = QFormLayout()

        #layout = QFormLayout()

        self.amount_input = QLineEdit()
        self.type_combobox = QComboBox()
        self.type_combobox.addItems(DEFAULT_SCHEDULE_C_CATEGORIES["expense"])
        self.date_input = QDateEdit()
        self.date_input.setCalendarPopup(True)
        self.date_input.setDate(QDate.currentDate())
        self.comments_input = QTextEdit()

        layout.addRow("Amount:", self.amount_input)
        layout.addRow("Type:", self.type_combobox)
        layout.addRow("Date:", self.date_input)
        layout.addRow("Comments:", self.comments_input)

        layout.addLayout(form_layout)

        # File attachments
        self.attach_button = QPushButton("Attach File")
        self.attach_button.clicked.connect(self.attach_file)
        layout.addWidget(self.attach_button)

        self.file_list = QListWidget()
        layout.addWidget(self.file_list)

        # Buttons
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.validate_and_accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        self.setLayout(layout)

        # Load data if editing existing expense
        if self.expense_data:
            self.load_expense_data()

    def attach_file(self):
        options = QFileDialog.Options()
        filename, _ = QFileDialog.getOpenFileName(
            self, "Select File", "", "All Files (*);;PDF Files (*.pdf);;Image Files (*.png *.jpg *.jpeg)", options=options)
        if filename:
            self.files.append(filename)
            self.file_list.addItem(os.path.basename(filename))

    def load_expense_data(self):
        data = self.expense_data
        self.amount_input.setText(str(data['amount']))
        self.type_combobox.setCurrentText(data['type'])
        self.date_input.setDate(QDate.fromString(data['date'], "yyyy-MM-dd"))
        self.comments_input.setPlainText(data['comments'])
        expense_id = self.expense_data.get('id')
        if expense_id:
            files = self.parent.db.get_expense_files(expense_id)
            for file in files:
                self.file_list.addItem(file['file_name'])
                self.files.append(file['file_path'])

    def validate_and_accept(self):
        if self.amount_input.text() == '':
            QMessageBox.warning(self, "Input Error", "Amount is required.")
            return
        self.accept()

    def get_data(self):
        data = {
            'amount': float(self.amount_input.text()),
            'type': self.type_combobox.currentText(),
            'date': self.date_input.date().toString("yyyy-MM-dd"),
            'comments': self.comments_input.toPlainText(),
            'files': self.files

        }
        return data

class ManageCustomersScreen(QWidget):
    """Screen for managing customers."""
    def __init__(self, parent):
        super().__init__()
        self.parent = parent

        layout = QVBoxLayout()

        # Table to display customers
        self.table_widget = QTableWidget()
        self.table_widget.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_widget.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_widget.setSelectionMode(QAbstractItemView.SingleSelection)
        layout.addWidget(self.table_widget)

        # Buttons for operations
        self.add_button = QPushButton("Add Customer")
        self.add_button.clicked.connect(self.add_customer)
        layout.addWidget(self.add_button)

        self.edit_button = QPushButton("Edit Customer")
        self.edit_button.clicked.connect(self.edit_customer)
        layout.addWidget(self.edit_button)

        self.delete_button = QPushButton("Delete Customer")
        self.delete_button.clicked.connect(self.delete_customer)
        layout.addWidget(self.delete_button)

        # Back button to return to Main Screen
        self.back_button = QPushButton("Back")
        self.back_button.clicked.connect(lambda: parent.show_screen("Main"))
        layout.addWidget(self.back_button)

        self.setLayout(layout)
        self.load_customers()

    def load_customers(self):
        customers = self.parent.db.get_customers()
        self.table_widget.setRowCount(len(customers))
        self.table_widget.setColumnCount(4)
        self.table_widget.setHorizontalHeaderLabels(["ID", "Child Name", "Enrollment Status", "Fee"])
        for row, customer in enumerate(customers):
            self.table_widget.setItem(row, 0, QTableWidgetItem(str(customer['id'])))
            self.table_widget.setItem(row, 1, QTableWidgetItem(customer.get('child_full_name', '')))
            self.table_widget.setItem(row, 2, QTableWidgetItem(customer.get('enrollment_status', '')))
            self.table_widget.setItem(row, 3, QTableWidgetItem(customer.get('fee', '')))


    def add_customer(self):
        dialog = CustomerDialog(self.parent, "Add Customer")
        if dialog.exec_():
            customer_data = dialog.get_data()
            self.parent.db.add_customer(customer_data)
            self.load_customers()

    def edit_customer(self):
        selected_items = self.table_widget.selectedItems()
        if selected_items:
            customer_id = int(selected_items[0].text())
            # Fetch the existing customer data
            customer_data = next((c for c in self.parent.db.get_customers() if c['id'] == customer_id), None)
            if customer_data:
                dialog = CustomerDialog(self.parent, "Edit Customer", customer_data)
                if dialog.exec_():
                    updated_customer_data = dialog.get_data()
                    self.parent.db.update_customer(customer_id, updated_customer_data)
                    self.load_customers()
        else:
            QMessageBox.warning(self, "Selection Error", "Please select a customer to edit.")


    def delete_customer(self):
        selected_items = self.table_widget.selectedItems()
        if selected_items:
            customer_id = int(selected_items[0].text())
            reply = QMessageBox.question(self, "Delete Customer", "Are you sure you want to delete this customer?",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.parent.db.delete_customer(customer_id)
                self.load_customers()
        else:
            QMessageBox.warning(self, "Selection Error", "Please select a customer to delete.")

class CustomerDialog(QDialog):
    """Dialog for adding/editing a customer with comprehensive details."""
    def __init__(self, parent, title, customer_data=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.customer_data = customer_data

        layout = QVBoxLayout()

        # Create a tab widget
        self.tabs = QTabWidget()

        # Child Information Tab
        self.child_tab = QWidget()
        self.init_child_tab()
        self.tabs.addTab(self.child_tab, "Child Information")

        # Parents Information Tab
        self.parents_tab = QWidget()
        self.init_parents_tab()
        self.tabs.addTab(self.parents_tab, "Parents Information")

        # Emergency Contacts Tab
        self.emergency_tab = QWidget()
        self.init_emergency_tab()
        self.tabs.addTab(self.emergency_tab, "Emergency Contacts")

        # Medical Information Tab
        self.medical_tab = QWidget()
        self.init_medical_tab()
        self.tabs.addTab(self.medical_tab, "Medical Information")

        # Consents Tab
        self.consents_tab = QWidget()
        self.init_consents_tab()
        self.tabs.addTab(self.consents_tab, "Consents")

        layout.addWidget(self.tabs)

        # Buttons
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.validate_and_accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        self.setLayout(layout)

        # Load data if editing existing customer
        if self.customer_data:
            self.load_customer_data()

    def init_child_tab(self):
        layout = QFormLayout()
        self.child_full_name = QLineEdit()
        self.enrollment_start_date = QDateEdit()
        self.enrollment_start_date.setCalendarPopup(True)
        self.enrollment_start_date.setDate(QDate.currentDate())
        self.fee = QLineEdit()
        self.enrollment_status = QComboBox()
        self.enrollment_status.addItems(["Enrolled", "Waitlisted", "Withdrawn"])
        layout.addRow("Full Name:", self.child_full_name)
        layout.addRow("Enrollment Start Date:", self.enrollment_start_date)
        layout.addRow("Fee:", self.fee)
        layout.addRow("Enrollment Status:", self.enrollment_status)
        self.child_tab.setLayout(layout)

    def init_parents_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Father Information
        father_group = QGroupBox("Father's Information")
        father_layout = QFormLayout()

        self.father_first_name = QLineEdit()
        self.father_middle_name = QLineEdit()
        self.father_last_name = QLineEdit()
        self.father_email = QLineEdit()
        self.father_phone = QLineEdit()
        self.father_address_line1 = QLineEdit()
        self.father_address_line2 = QLineEdit()
        self.father_city = QLineEdit()
        self.father_state = QLineEdit()
        self.father_postal_code = QLineEdit()

        father_layout.addRow("First Name:", self.father_first_name)
        father_layout.addRow("Middle Name:", self.father_middle_name)
        father_layout.addRow("Last Name:", self.father_last_name)
        father_layout.addRow("Email ID:", self.father_email)
        father_layout.addRow("Phone Number:", self.father_phone)
        father_layout.addRow("Address Line 1:", self.father_address_line1)
        father_layout.addRow("Address Line 2:", self.father_address_line2)
        father_layout.addRow("City:", self.father_city)
        father_layout.addRow("State Code:", self.father_state)
        father_layout.addRow("Postal Code:", self.father_postal_code)

        father_group.setLayout(father_layout)
        layout.addWidget(father_group)

        # Mother Information
        mother_group = QGroupBox("Mother's Information")
        mother_layout = QFormLayout()

        self.mother_same_address = QCheckBox("Same as Father's Address")
        self.mother_same_address.stateChanged.connect(self.copy_father_address)

        self.mother_first_name = QLineEdit()
        self.mother_middle_name = QLineEdit()
        self.mother_last_name = QLineEdit()
        self.mother_email = QLineEdit()
        self.mother_phone = QLineEdit()
        self.mother_address_line1 = QLineEdit()
        self.mother_address_line2 = QLineEdit()
        self.mother_city = QLineEdit()
        self.mother_state = QLineEdit()
        self.mother_postal_code = QLineEdit()

        mother_layout.addRow(self.mother_same_address)
        mother_layout.addRow("First Name:", self.mother_first_name)
        mother_layout.addRow("Middle Name:", self.mother_middle_name)
        mother_layout.addRow("Last Name:", self.mother_last_name)
        mother_layout.addRow("Email ID:", self.mother_email)
        mother_layout.addRow("Phone Number:", self.mother_phone)
        mother_layout.addRow("Address Line 1:", self.mother_address_line1)
        mother_layout.addRow("Address Line 2:", self.mother_address_line2)
        mother_layout.addRow("City:", self.mother_city)
        mother_layout.addRow("State Code:", self.mother_state)
        mother_layout.addRow("Postal Code:", self.mother_postal_code)

        mother_group.setLayout(mother_layout)
        layout.addWidget(mother_group)

        scroll.setWidget(widget)
        parent_layout = QVBoxLayout()
        parent_layout.addWidget(scroll)
        self.parents_tab.setLayout(parent_layout)

    def init_emergency_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.emergency_contacts = []
        for i in range(3):
            contact_group = QGroupBox(f"Emergency Contact {i+1}")
            contact_layout = QFormLayout()

            contact_name = QLineEdit()
            contact_address = QLineEdit()
            contact_phone = QLineEdit()
            contact_relationship = QLineEdit()

            contact_layout.addRow("Name:", contact_name)
            contact_layout.addRow("Address:", contact_address)
            contact_layout.addRow("Phone Number:", contact_phone)
            contact_layout.addRow("Relationship:", contact_relationship)

            contact_group.setLayout(contact_layout)
            layout.addWidget(contact_group)

            self.emergency_contacts.append({
                'name': contact_name,
                'address': contact_address,
                'phone': contact_phone,
                'relationship': contact_relationship
            })

        self.pickup_authorizations = []
        for i in range(3):
            pickup_group = QGroupBox(f"Pickup Authorization {i+1}")
            pickup_layout = QFormLayout()

            pickup_name = QLineEdit()
            pickup_phone = QLineEdit()
            pickup_relationship = QLineEdit()

            pickup_layout.addRow("Name:", pickup_name)
            pickup_layout.addRow("Phone Number:", pickup_phone)
            pickup_layout.addRow("Relationship:", pickup_relationship)

            pickup_group.setLayout(pickup_layout)
            layout.addWidget(pickup_group)

            self.pickup_authorizations.append({
                'name': pickup_name,
                'phone': pickup_phone,
                'relationship': pickup_relationship
            })

        scroll.setWidget(widget)
        emergency_layout = QVBoxLayout()
        emergency_layout.addWidget(scroll)
        self.emergency_tab.setLayout(emergency_layout)

    def init_medical_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Medical Information
        medical_group = QGroupBox("Medical Information")
        medical_layout = QFormLayout()

        self.medical_conditions = QTextEdit()
        self.allergies = QTextEdit()

        medical_layout.addRow("Medical Conditions:", self.medical_conditions)
        medical_layout.addRow("Allergies:", self.allergies)

        medical_group.setLayout(medical_layout)
        layout.addWidget(medical_group)

        # Medical Providers
        providers_group = QGroupBox("Medical Providers")
        providers_layout = QVBoxLayout()

        # Medical Care Provider
        medical_provider_group = QGroupBox("Medical Care Provider")
        medical_provider_layout = QFormLayout()

        self.medical_provider_name = QLineEdit()
        self.medical_provider_address = QLineEdit()
        self.medical_provider_phone = QLineEdit()
        self.medical_provider_last_exam_date = QDateEdit()
        self.medical_provider_last_exam_date.setCalendarPopup(True)

        medical_provider_layout.addRow("Name:", self.medical_provider_name)
        medical_provider_layout.addRow("Address:", self.medical_provider_address)
        medical_provider_layout.addRow("Phone Number:", self.medical_provider_phone)
        medical_provider_layout.addRow("Last Exam Date:", self.medical_provider_last_exam_date)

        medical_provider_group.setLayout(medical_provider_layout)
        providers_layout.addWidget(medical_provider_group)

        # Dental Care Provider
        dental_provider_group = QGroupBox("Dental Care Provider")
        dental_provider_layout = QFormLayout()

        self.dental_provider_name = QLineEdit()
        self.dental_provider_address = QLineEdit()
        self.dental_provider_phone = QLineEdit()
        self.dental_provider_last_exam_date = QDateEdit()
        self.dental_provider_last_exam_date.setCalendarPopup(True)

        dental_provider_layout.addRow("Name:", self.dental_provider_name)
        dental_provider_layout.addRow("Address:", self.dental_provider_address)
        dental_provider_layout.addRow("Phone Number:", self.dental_provider_phone)
        dental_provider_layout.addRow("Last Exam Date:", self.dental_provider_last_exam_date)

        dental_provider_group.setLayout(dental_provider_layout)
        providers_layout.addWidget(dental_provider_group)

        providers_group.setLayout(providers_layout)
        layout.addWidget(providers_group)

        # Preferred Emergency Care
        emergency_care_group = QGroupBox("Preferred Emergency Care")
        emergency_care_layout = QFormLayout()

        self.emergency_care_name = QLineEdit()
        self.emergency_care_address = QLineEdit()
        self.emergency_care_phone = QLineEdit()

        emergency_care_layout.addRow("Name:", self.emergency_care_name)
        emergency_care_layout.addRow("Address:", self.emergency_care_address)
        emergency_care_layout.addRow("Phone Number:", self.emergency_care_phone)

        emergency_care_group.setLayout(emergency_care_layout)
        layout.addWidget(emergency_care_group)

        scroll.setWidget(widget)
        medical_layout = QVBoxLayout()
        medical_layout.addWidget(scroll)
        self.medical_tab.setLayout(medical_layout)

    def init_consents_tab(self):
        layout = QFormLayout()

        self.consent_lip_balm = QCheckBox("Consent for Lip Balm")
        self.consent_lotion = QCheckBox("Consent for Lotion")
        self.consent_diaper_ointment = QCheckBox("Consent for Diaper Ointment")
        self.consent_sunscreen = QCheckBox("Consent for Sunscreen")
        self.consent_medicine = QCheckBox("Consent for Medicine")
        self.consent_photo = QCheckBox("Consent for Posting Photos Online")
        self.consent_meals = QCheckBox("Consent for Meals at Daycare")

        layout.addRow(self.consent_lip_balm)
        layout.addRow(self.consent_lotion)
        layout.addRow(self.consent_diaper_ointment)
        layout.addRow(self.consent_sunscreen)
        layout.addRow(self.consent_medicine)
        layout.addRow(self.consent_photo)
        layout.addRow(self.consent_meals)

        self.consents_tab.setLayout(layout)

    def copy_father_address(self):
        if self.mother_same_address.isChecked():
            self.mother_address_line1.setText(self.father_address_line1.text())
            self.mother_address_line2.setText(self.father_address_line2.text())
            self.mother_city.setText(self.father_city.text())
            self.mother_state.setText(self.father_state.text())
            self.mother_postal_code.setText(self.father_postal_code.text())
            # Disable mother's address fields
            self.mother_address_line1.setDisabled(True)
            self.mother_address_line2.setDisabled(True)
            self.mother_city.setDisabled(True)
            self.mother_state.setDisabled(True)
            self.mother_postal_code.setDisabled(True)
        else:
            # Enable mother's address fields
            self.mother_address_line1.setDisabled(False)
            self.mother_address_line2.setDisabled(False)
            self.mother_city.setDisabled(False)
            self.mother_state.setDisabled(False)
            self.mother_postal_code.setDisabled(False)

    def validate_and_accept(self):
        # Perform validation if necessary
        if self.child_full_name.text() == '':
            QMessageBox.warning(self, "Input Error", "Child's full name is required.")
            return
        self.accept()

    def get_data(self):
        """Collect data from all fields and return as a dictionary."""
        data = {
            'child_full_name': self.child_full_name.text(),
            'enrollment_start_date': self.enrollment_start_date.date().toString("yyyy-MM-dd"),
            'fee': self.fee.text(),
            'enrollment_status': self.enrollment_status.currentText(),
            'father': {
                'first_name': self.father_first_name.text(),
                'middle_name': self.father_middle_name.text(),
                'last_name': self.father_last_name.text(),
                'email': self.father_email.text(),
                'phone': self.father_phone.text(),
                'address_line1': self.father_address_line1.text(),
                'address_line2': self.father_address_line2.text(),
                'city': self.father_city.text(),
                'state': self.father_state.text(),
                'postal_code': self.father_postal_code.text()
            },
            'mother': {
                'first_name': self.mother_first_name.text(),
                'middle_name': self.mother_middle_name.text(),
                'last_name': self.mother_last_name.text(),
                'email': self.mother_email.text(),
                'phone': self.mother_phone.text(),
                'address_line1': self.mother_address_line1.text(),
                'address_line2': self.mother_address_line2.text(),
                'city': self.mother_city.text(),
                'state': self.mother_state.text(),
                'postal_code': self.mother_postal_code.text()
            },
            'emergency_contacts': [],
            'pickup_authorizations': [],
            'medical_conditions': self.medical_conditions.toPlainText(),
            'allergies': self.allergies.toPlainText(),
            'medical_provider': {
                'name': self.medical_provider_name.text(),
                'address': self.medical_provider_address.text(),
                'phone': self.medical_provider_phone.text(),
                'last_exam_date': self.medical_provider_last_exam_date.date().toString("yyyy-MM-dd")
            },
            'dental_provider': {
                'name': self.dental_provider_name.text(),
                'address': self.dental_provider_address.text(),
                'phone': self.dental_provider_phone.text(),
                'last_exam_date': self.dental_provider_last_exam_date.date().toString("yyyy-MM-dd")
            },
            'emergency_care': {
                'name': self.emergency_care_name.text(),
                'address': self.emergency_care_address.text(),
                'phone': self.emergency_care_phone.text()
            },
            'consents': {
                'lip_balm': self.consent_lip_balm.isChecked(),
                'lotion': self.consent_lotion.isChecked(),
                'diaper_ointment': self.consent_diaper_ointment.isChecked(),
                'sunscreen': self.consent_sunscreen.isChecked(),
                'medicine': self.consent_medicine.isChecked(),
                'photo': self.consent_photo.isChecked(),
                'meals': self.consent_meals.isChecked()
            }
        }

        for contact in self.emergency_contacts:
            data['emergency_contacts'].append({
                'name': contact['name'].text(),
                'address': contact['address'].text(),
                'phone': contact['phone'].text(),
                'relationship': contact['relationship'].text()
            })

        for pickup in self.pickup_authorizations:
            data['pickup_authorizations'].append({
                'name': pickup['name'].text(),
                'phone': pickup['phone'].text(),
                'relationship': pickup['relationship'].text()
            })

        return data

    def load_customer_data(self):
        """Load existing customer data into fields."""
        data = self.customer_data
        self.child_full_name.setText(data.get('child_full_name', ''))
        self.enrollment_start_date.setDate(QDate.fromString(data.get('enrollment_start_date', QDate.currentDate().toString("yyyy-MM-dd")), "yyyy-MM-dd"))
        self.fee.setText(data.get('fee', ''))
        self.enrollment_status.setCurrentText(data.get('enrollment_status', 'Enrolled'))

        father = data.get('father', {})
        self.father_first_name.setText(father.get('first_name', ''))
        self.father_middle_name.setText(father.get('middle_name', ''))
        self.father_last_name.setText(father.get('last_name', ''))
        self.father_email.setText(father.get('email', ''))
        self.father_phone.setText(father.get('phone', ''))
        self.father_address_line1.setText(father.get('address_line1', ''))
        self.father_address_line2.setText(father.get('address_line2', ''))
        self.father_city.setText(father.get('city', ''))
        self.father_state.setText(father.get('state', ''))
        self.father_postal_code.setText(father.get('postal_code', ''))

        mother = data.get('mother', {})
        self.mother_first_name.setText(mother.get('first_name', ''))
        self.mother_middle_name.setText(mother.get('middle_name', ''))
        self.mother_last_name.setText(mother.get('last_name', ''))
        self.mother_email.setText(mother.get('email', ''))
        self.mother_phone.setText(mother.get('phone', ''))
        self.mother_address_line1.setText(mother.get('address_line1', ''))
        self.mother_address_line2.setText(mother.get('address_line2', ''))
        self.mother_city.setText(mother.get('city', ''))
        self.mother_state.setText(mother.get('state', ''))
        self.mother_postal_code.setText(mother.get('postal_code', ''))

        if (self.mother_address_line1.text() == self.father_address_line1.text() and
            self.mother_city.text() == self.father_city.text() and
            self.mother_state.text() == self.father_state.text() and
            self.mother_postal_code.text() == self.father_postal_code.text()):
            self.mother_same_address.setChecked(True)
            self.copy_father_address()

        emergency_contacts = data.get('emergency_contacts', [])
        for i, contact in enumerate(emergency_contacts):
            if i < len(self.emergency_contacts):
                self.emergency_contacts[i]['name'].setText(contact.get('name', ''))
                self.emergency_contacts[i]['address'].setText(contact.get('address', ''))
                self.emergency_contacts[i]['phone'].setText(contact.get('phone', ''))
                self.emergency_contacts[i]['relationship'].setText(contact.get('relationship', ''))

        pickup_authorizations = data.get('pickup_authorizations', [])
        for i, pickup in enumerate(pickup_authorizations):
            if i < len(self.pickup_authorizations):
                self.pickup_authorizations[i]['name'].setText(pickup.get('name', ''))
                self.pickup_authorizations[i]['phone'].setText(pickup.get('phone', ''))
                self.pickup_authorizations[i]['relationship'].setText(pickup.get('relationship', ''))

        self.medical_conditions.setPlainText(data.get('medical_conditions', ''))
        self.allergies.setPlainText(data.get('allergies', ''))

        medical_provider = data.get('medical_provider', {})
        self.medical_provider_name.setText(medical_provider.get('name', ''))
        self.medical_provider_address.setText(medical_provider.get('address', ''))
        self.medical_provider_phone.setText(medical_provider.get('phone', ''))
        self.medical_provider_last_exam_date.setDate(QDate.fromString(medical_provider.get('last_exam_date', QDate.currentDate().toString("yyyy-MM-dd")), "yyyy-MM-dd"))

        dental_provider = data.get('dental_provider', {})
        self.dental_provider_name.setText(dental_provider.get('name', ''))
        self.dental_provider_address.setText(dental_provider.get('address', ''))
        self.dental_provider_phone.setText(dental_provider.get('phone', ''))
        self.dental_provider_last_exam_date.setDate(QDate.fromString(dental_provider.get('last_exam_date', QDate.currentDate().toString("yyyy-MM-dd")), "yyyy-MM-dd"))

        emergency_care = data.get('emergency_care', {})
        self.emergency_care_name.setText(emergency_care.get('name', ''))
        self.emergency_care_address.setText(emergency_care.get('address', ''))
        self.emergency_care_phone.setText(emergency_care.get('phone', ''))

        consents = data.get('consents', {})
        self.consent_lip_balm.setChecked(consents.get('lip_balm', False))
        self.consent_lotion.setChecked(consents.get('lotion', False))
        self.consent_diaper_ointment.setChecked(consents.get('diaper_ointment', False))
        self.consent_sunscreen.setChecked(consents.get('sunscreen', False))
        self.consent_medicine.setChecked(consents.get('medicine', False))
        self.consent_photo.setChecked(consents.get('photo', False))
        self.consent_meals.setChecked(consents.get('meals', False))

class ManageEmployeesScreen(QWidget):
    """Screen for managing employees."""
    def __init__(self, parent):
        super().__init__()
        self.parent = parent

        layout = QVBoxLayout()

        # Table to display employees
        self.table_widget = QTableWidget()
        self.table_widget.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_widget.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_widget.setSelectionMode(QAbstractItemView.SingleSelection)
        layout.addWidget(self.table_widget)

        # Buttons for operations
        self.add_button = QPushButton("Add Employee")
        self.add_button.clicked.connect(self.add_employee)
        layout.addWidget(self.add_button)

        self.edit_button = QPushButton("Edit Employee")
        self.edit_button.clicked.connect(self.edit_employee)
        layout.addWidget(self.edit_button)

        self.delete_button = QPushButton("Delete Employee")
        self.delete_button.clicked.connect(self.delete_employee)
        layout.addWidget(self.delete_button)

        # Back button to return to Main Screen
        self.back_button = QPushButton("Back")
        self.back_button.clicked.connect(lambda: parent.show_screen("Main"))
        layout.addWidget(self.back_button)

        self.setLayout(layout)
        self.load_employees()

    def load_employees(self):
        employees = self.parent.db.get_employees()
        self.table_widget.setRowCount(len(employees))
        self.table_widget.setColumnCount(4)
        self.table_widget.setHorizontalHeaderLabels(["ID", "Name", "Contact Info", "Comments"])
        for row, employee in enumerate(employees):
            for col, value in enumerate(employee):
                self.table_widget.setItem(row, col, QTableWidgetItem(str(value)))

    def add_employee(self):
        dialog = EmployeeDialog(self.parent, "Add Employee")
        if dialog.exec_():
            name, contact_info, comments = dialog.get_data()
            self.parent.db.add_employee(name, contact_info, comments)
            self.load_employees()

    def edit_employee(self):
        selected_items = self.table_widget.selectedItems()
        if selected_items:
            employee_id = int(selected_items[0].text())
            name = selected_items[1].text()
            contact_info = selected_items[2].text()
            comments = selected_items[3].text()

            dialog = EmployeeDialog(self.parent, "Edit Employee", name, contact_info, comments)
            if dialog.exec_():
                name, contact_info, comments = dialog.get_data()
                self.parent.db.update_employee(employee_id, name, contact_info, comments)
                self.load_employees()
        else:
            QMessageBox.warning(self, "Selection Error", "Please select an employee to edit.")

    def delete_employee(self):
        selected_items = self.table_widget.selectedItems()
        if selected_items:
            employee_id = int(selected_items[0].text())
            reply = QMessageBox.question(self, "Delete Employee", "Are you sure you want to delete this employee?",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.parent.db.delete_employee(employee_id)
                self.load_employees()
        else:
            QMessageBox.warning(self, "Selection Error", "Please select an employee to delete.")

class EmployeeDialog(QDialog):
    """Dialog for adding/editing an employee with comprehensive details."""
    def __init__(self, parent, title, employee_data=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.employee_data = employee_data

        layout = QVBoxLayout()

        # Personal Information
        personal_group = QGroupBox("Personal Information")
        personal_layout = QFormLayout()
        self.name_input = QLineEdit()
        self.address_input = QLineEdit()
        self.contact_input = QLineEdit()
        self.email_input = QLineEdit()
        personal_layout.addRow("Name:", self.name_input)
        personal_layout.addRow("Address:", self.address_input)
        personal_layout.addRow("Contact Number:", self.contact_input)
        personal_layout.addRow("Email:", self.email_input)
        personal_group.setLayout(personal_layout)
        layout.addWidget(personal_group)

        # # Employment Details
        # employment_group = QGroupBox("Employment Details")
        # employment_layout = QFormLayout()
        # self.hire_status_combobox = QComboBox()
        # self.hire_status_combobox.addItems(["Candidate", "Hired", "On Probation", "Permanent"])
        # self.education_input = QLineEdit()
        # self.experience_input = QTextEdit()
        # self.referral_input = QLineEdit()
        # employment_layout.addRow("Hire Status:", self.hire_status_combobox)
        # employment_layout.addRow("Educational Qualification:", self.education_input)
        # employment_layout.addRow("Prior Experience:", self.experience_input)
        # employment_layout.addRow("Referral:", self.referral_input)
        # employment_group.setLayout(employment_layout)
        # layout.addWidget(employment_group)

        # # Emergency Contact
        # emergency_group = QGroupBox("Emergency Contact")
        # emergency_layout = QFormLayout()
        # self.emergency_contact_name = QLineEdit()
        # self.emergency_contact_relationship = QLineEdit()
        # self.emergency_contact_phone = QLineEdit()
        # emergency_layout.addRow("Name:", self.emergency_contact_name)
        # emergency_layout.addRow("Relationship:", self.emergency_contact_relationship)
        # emergency_layout.addRow("Phone Number:", self.emergency_contact_phone)
        # emergency_group.setLayout(emergency_layout)
        # layout.addWidget(emergency_group)

        # Buttons
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        self.setLayout(layout)

        # Load data if editing existing employee
        if self.employee_data:
            self.load_employee_data()

    def get_data(self):
        """Collect and return all employee data as a dictionary."""
        data = {
            'name': self.name_input.text(),
            'address': self.name.input.text(),
            'contact_info': self.contact_input.text(),
            'comments': self.comments_input.toPlainText()
            #,  # Replace with your form's field names
            # 'hire_status': self.hire_status_combobox.currentText(),
            # 'education': self.education_input.text(),
            # 'experience': self.experience_input.toPlainText(),
            # 'emergency_contact': {
            #     'name': self.emergency_contact_name.text(),
            #     'relationship': self.emergency_contact_relationship.text(),
            #     'phone': self.emergency_contact_phone.text(),
            }

        return data

    def load_employee_data(self):
        """Load existing employee data into fields."""
        data = self.employee_data
        self.name_input.setText(data.get('name', ''))
        self.address_input.setText(data.get('address', ''))
        self.contact_input.setText(data.get('contact', ''))
        self.email_input.setText(data.get('email', ''))
        # self.hire_status_combobox.setCurrentText(data.get('hire_status', 'Candidate'))
        # self.education_input.setText(data.get('education', ''))
        # self.experience_input.setPlainText(data.get('experience', ''))
        # self.referral_input.setText(data.get('referral', ''))
        # emergency_contact = data.get('emergency_contact', {})
        # self.emergency_contact_name.setText(emergency_contact.get('name', ''))
        # self.emergency_contact_relationship.setText(emergency_contact.get('relationship', ''))
        # self.emergency_contact_phone.setText(emergency_contact.get('phone', ''))

class BalanceSheetScreen(QWidget):
    """Screen for viewing balance sheet report."""
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        layout = QVBoxLayout()

        # Date selection
        date_layout = QHBoxLayout()
        self.date_label = QLabel("As of Date:")
        date_layout.addWidget(self.date_label)
        self.as_of_date = QDateEdit()
        self.as_of_date.setCalendarPopup(True)
        self.as_of_date.setDate(QDate.currentDate())
        date_layout.addWidget(self.as_of_date)

        self.generate_button = QPushButton("Generate Balance Sheet")
        self.generate_button.clicked.connect(self.generate_report)
        date_layout.addWidget(self.generate_button)

        layout.addLayout(date_layout)

        # Report display
        self.report_text = QTextEdit()
        self.report_text.setReadOnly(True)
        layout.addWidget(self.report_text)

        # Back button to return to Main Screen
        self.back_button = QPushButton("Back")
        self.back_button.clicked.connect(lambda: parent.show_screen("Main"))
        layout.addWidget(self.back_button)

        self.setLayout(layout)

    def generate_report(self):
        as_of_date = self.as_of_date.date().toString("yyyy-MM-dd")

        # Calculate total assets (e.g., total income up to the date)
        total_assets = self.get_total("income", "1900-01-01", as_of_date)
        # Calculate total liabilities (e.g., total expenses up to the date)
        total_liabilities = self.get_total("expense", "1900-01-01", as_of_date)
        # For simplicity, assuming equity = assets - liabilities
        total_equity = total_assets - total_liabilities

        report = f"Balance Sheet Report\n"
        report += f"As of: {as_of_date}\n\n"
        report += f"Total Assets: ${total_assets:.2f}\n"
        report += f"Total Liabilities: ${total_liabilities:.2f}\n"
        report += f"Total Equity: ${total_equity:.2f}\n"

        self.report_text.setText(report)

    def get_total(self, table, start_date, end_date):
        try:
            query = f"SELECT SUM(amount) FROM {table} WHERE date BETWEEN ? AND ?"
            self.parent.db.cursor.execute(query, (start_date, end_date))
            result = self.parent.db.cursor.fetchone()[0]
            return result if result else 0.0
        except sqlite3.Error as e:
            QMessageBox.critical(self, "Database Error", f"Error calculating total {table}: {e}")
            return 0.0

class CashFlowScreen(QWidget):
    """Screen for viewing cash flow statement."""
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        layout = QVBoxLayout()

        # Date range selection
        date_layout = QHBoxLayout()
        self.start_date_label = QLabel("Start Date:")
        date_layout.addWidget(self.start_date_label)
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDate(QDate.currentDate().addMonths(-1))
        date_layout.addWidget(self.start_date)

        self.end_date_label = QLabel("End Date:")
        date_layout.addWidget(self.end_date_label)
        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDate(QDate.currentDate())
        date_layout.addWidget(self.end_date)

        self.generate_button = QPushButton("Generate Cash Flow Statement")
        self.generate_button.clicked.connect(self.generate_report)
        date_layout.addWidget(self.generate_button)

        layout.addLayout(date_layout)

        # Report display
        self.report_text = QTextEdit()
        self.report_text.setReadOnly(True)
        layout.addWidget(self.report_text)

        # Back button
        self.back_button = QPushButton("Back")
        self.back_button.clicked.connect(lambda: parent.show_screen("Main"))
        layout.addWidget(self.back_button)

        self.setLayout(layout)

    def generate_report(self):
        start_date = self.start_date.date().toString("yyyy-MM-dd")
        end_date = self.end_date.date().toString("yyyy-MM-dd")

        # For simplicity, net cash flow = income - expenses in the period
        total_income = self.get_total("income", start_date, end_date)
        total_expenses = self.get_total("expense", start_date, end_date)
        net_cash_flow = total_income - total_expenses

        report = f"Cash Flow Statement\n"
        report += f"Period: {start_date} to {end_date}\n\n"
        report += f"Cash Inflows:\n"
        report += f"  Total Income: ${total_income:.2f}\n\n"
        report += f"Cash Outflows:\n"
        report += f"  Total Expenses: ${total_expenses:.2f}\n\n"
        report += f"Net Cash Flow: ${net_cash_flow:.2f}\n"

        self.report_text.setText(report)

    def get_total(self, table, start_date, end_date):
        try:
            query = f"SELECT SUM(amount) FROM {table} WHERE date BETWEEN ? AND ?"
            self.parent.db.cursor.execute(query, (start_date, end_date))
            result = self.parent.db.cursor.fetchone()[0]
            return result if result else 0.0
        except sqlite3.Error as e:
            QMessageBox.critical(self, "Database Error", f"Error calculating total {table}: {e}")
            return 0.0

class TaxSummaryScreen(QWidget):
    """Screen for viewing tax summary report."""
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        layout = QVBoxLayout()

        # Period selection
        period_layout = QHBoxLayout()
        self.period_label = QLabel("Select Period:")
        period_layout.addWidget(self.period_label)
        self.period_combobox = QComboBox()
        self.period_combobox.addItems(["Quarterly", "Annual"])
        period_layout.addWidget(self.period_combobox)

        self.year_label = QLabel("Year:")
        period_layout.addWidget(self.year_label)
        self.year_input = QLineEdit()
        period_layout.addWidget(self.year_input)

        self.generate_button = QPushButton("Generate Tax Summary")
        self.generate_button.clicked.connect(self.generate_report)
        period_layout.addWidget(self.generate_button)

        layout.addLayout(period_layout)

        # Report display
        self.report_text = QTextEdit()
        self.report_text.setReadOnly(True)
        layout.addWidget(self.report_text)

        # Back button
        self.back_button = QPushButton("Back")
        self.back_button.clicked.connect(lambda: parent.show_screen("Main"))
        layout.addWidget(self.back_button)

        self.setLayout(layout)

    def generate_report(self):
        period = self.period_combobox.currentText()
        year = self.year_input.text()

        if not year.isdigit():
            QMessageBox.warning(self, "Input Error", "Please enter a valid year.")
            return

        year = int(year)
        if period == "Quarterly":
            # For simplicity, we'll show all quarters
            report = f"Tax Summary Report - Quarterly for {year}\n\n"
            for q in range(1, 5):
                start_date = QDate(year, 3 * q - 2, 1).toString("yyyy-MM-dd")
                end_month = 3 * q
                end_day = QDate(year, end_month, 1).daysInMonth()
                end_date = QDate(year, end_month, end_day).toString("yyyy-MM-dd")
                total_income = self.get_total("income", start_date, end_date)
                total_expenses = self.get_total("expense", start_date, end_date)
                taxable_income = total_income - total_expenses

                report += f"Quarter {q}:\n"
                report += f"  Total Income: ${total_income:.2f}\n"
                report += f"  Total Expenses: ${total_expenses:.2f}\n"
                report += f"  Taxable Income: ${taxable_income:.2f}\n\n"
        else:
            start_date = QDate(year, 1, 1).toString("yyyy-MM-dd")
            end_date = QDate(year, 12, 31).toString("yyyy-MM-dd")
            total_income = self.get_total("income", start_date, end_date)
            total_expenses = self.get_total("expense", start_date, end_date)
            taxable_income = total_income - total_expenses

            report = f"Tax Summary Report - Annual for {year}\n\n"
            report += f"Total Income: ${total_income:.2f}\n"
            report += f"Total Expenses: ${total_expenses:.2f}\n"
            report += f"Taxable Income: ${taxable_income:.2f}\n"

        self.report_text.setText(report)

    def get_total(self, table, start_date, end_date):
        try:
            query = f"SELECT SUM(amount) FROM {table} WHERE date BETWEEN ? AND ?"
            self.parent.db.cursor.execute(query, (start_date, end_date))
            result = self.parent.db.cursor.fetchone()[0]
            return result if result else 0.0
        except sqlite3.Error as e:
            QMessageBox.critical(self, "Database Error", f"Error calculating total {table}: {e}")
            return 0.0

class ProfitLossScreen(QWidget):
    """Screen for viewing profit and loss report."""
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        layout = QVBoxLayout()

        # Date range selection
        date_layout = QHBoxLayout()
        self.start_date_label = QLabel("Start Date:")
        date_layout.addWidget(self.start_date_label)
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDate(QDate.currentDate().addMonths(-1))
        date_layout.addWidget(self.start_date)

        self.end_date_label = QLabel("End Date:")
        date_layout.addWidget(self.end_date_label)
        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDate(QDate.currentDate())
        date_layout.addWidget(self.end_date)

        self.generate_button = QPushButton("Generate Report")
        self.generate_button.clicked.connect(self.generate_report)
        date_layout.addWidget(self.generate_button)

        layout.addLayout(date_layout)

        # Report display
        self.report_text = QTextEdit()
        self.report_text.setReadOnly(True)
        layout.addWidget(self.report_text)

        # Back button to return to Main Screen
        self.back_button = QPushButton("Back")
        self.back_button.clicked.connect(lambda: parent.show_screen("Main"))
        layout.addWidget(self.back_button)

        self.setLayout(layout)

    def generate_report(self):
        start_date = self.start_date.date().toString("yyyy-MM-dd")
        end_date = self.end_date.date().toString("yyyy-MM-dd")

        # Get total income
        total_income = self.get_total("income", start_date, end_date)
        # Get total expenses
        total_expenses = self.get_total("expense", start_date, end_date)

        profit_loss = total_income - total_expenses

        report = f"Profit and Loss Report\n"
        report += f"Period: {start_date} to {end_date}\n\n"
        report += f"Total Income: ${total_income:.2f}\n"
        report += f"Total Expenses: ${total_expenses:.2f}\n"
        report += f"Net Profit/Loss: ${profit_loss:.2f}\n"

        self.report_text.setText(report)

    def get_total(self, table, start_date, end_date):
        try:
            query = f"SELECT SUM(amount) FROM {table} WHERE date BETWEEN ? AND ?"
            self.parent.db.cursor.execute(query, (start_date, end_date))
            result = self.parent.db.cursor.fetchone()[0]
            return result if result else 0.0
        except sqlite3.Error as e:
            QMessageBox.critical(self, "Database Error", f"Error calculating total {table}: {e}")
            return 0.0

# Main entry point
def main():
    app = QApplication(sys.argv)
    window = IncomeExpenseApp()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()