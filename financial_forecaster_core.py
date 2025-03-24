#!/usr/bin/env python3
"""
Financial Forecaster Core Module
===============================

Core class for creating and managing the financial forecaster Excel workbook.
"""

import pandas as pd
import numpy as np
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Border, Side, Alignment, Protection
from openpyxl.formatting.rule import ColorScaleRule, CellIsRule
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from datetime import datetime, timedelta
import calendar

class FinancialForecaster:
    """Core class for creating and managing the financial forecaster Excel workbook"""
    
    def __init__(self):
        """Initialize the financial forecaster with default settings"""
        self.wb = Workbook()
        
        # Initialize worksheets
        self.transaction_types_sheet = self.wb.active
        self.transaction_types_sheet.title = "TransactionTypes"
        
        self.debts_sheet = self.wb.create_sheet("Debts")
        self.recurring_transactions_sheet = self.wb.create_sheet("RecurringTransactions")
        self.forecast_sheet = self.wb.create_sheet("Forecast")
        
        # Define some standard formatting
        self.header_font = Font(bold=True)
        self.currency_format = '_($* #,##0.00_);_($* (#,##0.00);_($* "-"??_);_(@_)'
        self.date_format = 'mm/dd/yyyy'
        self.percent_format = '0.00%'
        
        # Define transaction types from the reference data
        self.transaction_types = [
            ["Type", "Common Terms", "Balance Effect", "Category", "Account Type"],
            ["Purchase", "Purchase, Charge, Expense", "Increases", "Expense", "Credit"],
            ["Payment", "Payment, Credit", "Decreases", "Liability Payment", "Credit"],
            ["Refund", "Refund, Reversal", "Decreases", "Expense Reversal", "Credit"],
            ["Interest", "Interest, Finance Charge", "Increases", "Expense", "Credit"],
            ["Fee", "Late Fee, Annual Fee, etc.", "Increases", "Expense", "Credit"],
            ["Cash Advance", "Cash Advance", "Increases", "Liability", "Credit"],
            ["Balance Transfer", "Balance Transfer", "Depends", "Liability Transfer", "Credit"],
            ["Credit (Manual)", "Adjustment, Reimbursement", "Decreases", "Liability Credit", "Credit"],
            ["Rewards Statement Credit", "Cashback, Statement Credit", "Decreases", "Miscellaneous/Income", "Credit"],
            ["Deposit", "Deposit, Direct Deposit, Credit", "Increases", "Income / Transfer In", "Debit"],
            ["Withdrawal", "Withdrawal, ATM, Debit", "Decreases", "Cash / Personal", "Debit"],
            ["Debit Card Purchase", "POS, Debit, Card Purchase", "Decreases", "Expense", "Debit"],
            ["Bill/Online Payment", "ACH, Bill Pay, Electronic Payment", "Decreases", "Bills/Utilities/etc", "Debit"],
            ["Bank Fee", "Maintenance, Overdraft, NSF", "Decreases", "Bank Fees", "Debit"],
            ["Transfer (In/Out)", "ACH, Zelle, Venmo, Internal", "+/-", "Transfer In/Out", "Debit"],
            ["Refund/Reimbursement", "Refund, Reimbursement", "Increases", "Expense Reversal", "Debit"],
            ["Interest Earned", "Interest, Interest Payment", "Increases", "Interest Income", "Debit"],
            ["Mobile Deposit", "Mobile Deposit, Check", "Increases", "Income / Transfer In", "Debit"], 
            ["Pending Transaction", "Authorization, Pending", "Pending", "Temporary / Unknown", "Debit"]
        ]      
        # Define account names (placeholders, will be customizable)
        self.accounts = ["Checking Account", "Visa-CC", "Amex-CC", "Discover", "Citi", "CapitolOne"]
    
    def create_transaction_types_sheet(self):
        """Create the transaction types reference sheet"""
        ws = self.transaction_types_sheet
        
        # Add transaction types data
        for row_idx, row_data in enumerate(self.transaction_types, 1):
            for col_idx, cell_value in enumerate(row_data, 1):
                cell = ws.cell(row=row_idx, column=col_idx, value=cell_value)
                if row_idx == 1:  # Header row
                    cell.font = self.header_font
        
        # Apply formatting
        for col in range(1, 6):
            ws.column_dimensions[get_column_letter(col)].width = 20
            
        # Add table styling
        light_blue_fill = PatternFill(start_color="E6F2FF", end_color="E6F2FF", fill_type="solid")
        for row in range(2, len(self.transaction_types) + 1):
            if row % 2 == 0:  # Even rows
                for col in range(1, 6):
                    ws.cell(row=row, column=col).fill = light_blue_fill
        
        # Freeze the header row
        ws.freeze_panes = "A2"
        
        return ws
    
    def create_debts_sheet(self):
        """Create the debt information sheet"""
        ws = self.debts_sheet
        
        # Create headers
        headers = ["Account", "Current Balance", "Credit Limit", "Interest Rate", 
                   "Statement Close Day", "Payment Due Day", "Min Payment %", "Min Payment Fixed"]
        for col_idx, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_idx, value=header)
            cell.font = self.header_font
        
        # Add example credit card accounts
        credit_accounts = [acc for acc in self.accounts if "CC" in acc or acc in ["Discover", "Citi", "CapitolOne"]]
        for row_idx, account in enumerate(credit_accounts, 2):
            ws.cell(row=row_idx, column=1, value=account)
            ws.cell(row=row_idx, column=2, value=0)  # Default balance
            ws.cell(row=row_idx, column=3, value=10000)  # Default credit limit
            ws.cell(row=row_idx, column=4, value=0.1899)  # Default APR (18.99%)
            ws.cell(row=row_idx, column=5, value=15)  # Default statement close day
            ws.cell(row=row_idx, column=6, value=10)  # Default payment due day
            ws.cell(row=row_idx, column=7, value=0.02)  # Default min payment % (2%)
            ws.cell(row=row_idx, column=8, value=25)  # Default min payment fixed amount
        
        # Format columns
        ws.column_dimensions[get_column_letter(1)].width = 15  # Account
        ws.column_dimensions[get_column_letter(2)].width = 15  # Balance
        ws.column_dimensions[get_column_letter(3)].width = 15  # Credit Limit
        ws.column_dimensions[get_column_letter(4)].width = 15  # Interest Rate
        
        # Format cells
        for row in range(2, len(credit_accounts) + 2):
            # Format currency columns
            ws.cell(row=row, column=2).number_format = self.currency_format
            ws.cell(row=row, column=3).number_format = self.currency_format
            ws.cell(row=row, column=8).number_format = self.currency_format
            
            # Format percentage columns
            ws.cell(row=row, column=4).number_format = self.percent_format
            ws.cell(row=row, column=7).number_format = self.percent_format
        
        # Freeze the header row
        ws.freeze_panes = "A2"
        
        return ws
    
    def create_recurring_transactions_sheet(self):
        """Create the recurring transactions configuration sheet"""
        ws = self.recurring_transactions_sheet
        
        # Create headers
        headers = [
            "Type", "Transaction", "From", "To", "Amount", 
            "Frequency", "Start Date", "End Type", "End Date/Count", 
            "Monthly Day", "Weekly Day", "Active"
        ]
        
        for col_idx, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_idx, value=header)
            cell.font = self.header_font
        
        # Set column widths
        column_widths = [15, 25, 15, 15, 15, 15, 15, 15, 15, 12, 12, 10]
        for col_idx, width in enumerate(column_widths, 1):
            ws.column_dimensions[get_column_letter(col_idx)].width = width
        
        # Add data validation for Type column
        type_validation = DataValidation(
            type="list", 
            formula1=f"=TransactionTypes!$A$2:$A${len(self.transaction_types)}"
        )
        ws.add_data_validation(type_validation)
        for row in range(2, 101):  # Allow up to 100 recurring transactions
            type_validation.add(f"A{row}")
        
        # Add data validation for From and To columns
        account_list = ", ".join([f'"{acc}"' for acc in self.accounts + ["External"]])
        account_validation = DataValidation(type="list", formula1=f"={account_list}")
        ws.add_data_validation(account_validation)
        for row in range(2, 101):
            account_validation.add(f"C{row}")
            account_validation.add(f"D{row}")
        
        # Add data validation for Frequency
        freq_validation = DataValidation(
            type="list", 
            formula1='"Daily, Weekly, Bi-Weekly, Monthly, Quarterly, Semi-Annual, Annual"'
        )
        ws.add_data_validation(freq_validation)
        for row in range(2, 101):
            freq_validation.add(f"F{row}")
        
        # Add data validation for End Type
        end_type_validation = DataValidation(
            type="list", 
            formula1='"Date, Count, Indefinite"'
        )
        ws.add_data_validation(end_type_validation)
        for row in range(2, 101):
            end_type_validation.add(f"H{row}")
        
        # Add data validation for Weekly Day
        day_validation = DataValidation(
            type="list", 
            formula1='"Mon, Tue, Wed, Thu, Fri, Sat, Sun"'
        )
        ws.add_data_validation(day_validation)
        for row in range(2, 101):
            day_validation.add(f"K{row}")
        
        # Add data validation for Active
        active_validation = DataValidation(
            type="list", 
            formula1='"Yes, No"'
        )
        ws.add_data_validation(active_validation)
        for row in range(2, 101):
            active_validation.add(f"L{row}")
        
        # Add example recurring transactions
        example_data = [
            ["Deposit", "Paycheck", "External", "Checking Account", 2000, "Bi-Weekly", datetime.now(), "Indefinite", "", "", "Fri", "Yes"],
            ["Bill/Online Payment", "Rent", "Checking Account", "External", 1200, "Monthly", datetime.now(), "Indefinite", "", "1", "", "Yes"],
            ["Debit Card Purchase", "Groceries", "Checking Account", "External", 150, "Weekly", datetime.now(), "Indefinite", "", "", "Mon", "Yes"],
            ["Payment", "Credit Card Payment", "Checking Account", "Visa-CC", 500, "Monthly", datetime.now(), "Indefinite", "", "15", "", "Yes"]
        ]
        
        for row_idx, row_data in enumerate(example_data, 2):
            for col_idx, cell_value in enumerate(row_data, 1):
                ws.cell(row=row_idx, column=col_idx, value=cell_value)
                
                # Format date cells
                if col_idx == 7:  # Start Date
                    ws.cell(row=row_idx, column=col_idx).number_format = self.date_format
                elif col_idx == 9:  # End Date/Count
                    if isinstance(cell_value, datetime):
                        ws.cell(row=row_idx, column=col_idx).number_format = self.date_format
                
                # Format amount as currency
                if col_idx == 5:  # Amount
                    ws.cell(row=row_idx, column=col_idx).number_format = self.currency_format
        
        # Freeze the header row
        ws.freeze_panes = "A2"
        
        return ws
    
    def create_forecast_sheet(self):
        """Create the main forecast sheet with account balance projections"""
        ws = self.forecast_sheet
        
        # Create header for transaction details
        transaction_headers = ["Date", "Transaction", "Type", "From", "To", "Amount"]
        for col_idx, header in enumerate(transaction_headers, 1):
            cell = ws.cell(row=1, column=col_idx, value=header)
            cell.font = self.header_font
        
        # Create header for account balances
        for col_idx, account in enumerate(self.accounts, len(transaction_headers) + 1):
            cell = ws.cell(row=1, column=col_idx, value=account)
            cell.font = self.header_font
        
        # Set column widths
        ws.column_dimensions[get_column_letter(1)].width = 12  # Date
        ws.column_dimensions[get_column_letter(2)].width = 30  # Transaction
        ws.column_dimensions[get_column_letter(3)].width = 15  # Type
        ws.column_dimensions[get_column_letter(4)].width = 15  # From
        ws.column_dimensions[get_column_letter(5)].width = 15  # To
        ws.column_dimensions[get_column_letter(6)].width = 15  # Amount
        
        for col_idx, account in enumerate(self.accounts, len(transaction_headers) + 1):
            ws.column_dimensions[get_column_letter(col_idx)].width = 15  # Account balance columns
        
        # Add starting balances row
        ws.cell(row=2, column=1, value=datetime.now())
        ws.cell(row=2, column=2, value="Starting Balances")
        ws.cell(row=2, column=3, value="Initial")
        
        # Set initial account balances (placeholder values)
        for col_idx, account in enumerate(self.accounts, len(transaction_headers) + 1):
            if "CC" in account or account in ["Discover", "Citi", "CapitolOne"]:
                # Credit card accounts start with 0 balance (or link to Debts sheet)
                ws.cell(row=2, column=col_idx, value=0)
            else:
                # Checking account starts with 1000 (example)
                ws.cell(row=2, column=col_idx, value=1000)
        
        # Format cells
        for col_idx in range(len(transaction_headers) + 1, len(transaction_headers) + len(self.accounts) + 1):
            ws.cell(row=2, column=col_idx).number_format = self.currency_format
        
        # Format date column
        ws.cell(row=2, column=1).number_format = self.date_format
        
        # Format amount column
        ws.cell(row=2, column=6).number_format = self.currency_format
        
        # Add conditional formatting for negative balances
        for col_idx, account in enumerate(self.accounts, len(transaction_headers) + 1):
            # Red fill for negative balances
            red_rule = CellIsRule(
                operator='lessThan',
                formula=['0'],
                stopIfTrue=False,
                fill=PatternFill(start_color='FFCCCC', end_color='FFCCCC', fill_type='solid')
            )
            col_letter = get_column_letter(col_idx)
            ws.conditional_formatting.add(f"{col_letter}2:{col_letter}1000", red_rule)
        
        # Freeze headers
        ws.freeze_panes = "A2"
        
        # Add placeholder message
        ws.cell(row=4, column=1, value="Run the populate_forecast_from_recurring() function to populate this forecast.")
        ws.merge_cells(start_row=4, start_column=1, end_row=4, end_column=6)
        
        return ws
    
    def create_workbook(self):
        """Create the complete workbook"""
        # Create the sheets
        self.create_transaction_types_sheet()
        self.create_debts_sheet()
        self.create_recurring_transactions_sheet()
        self.create_forecast_sheet()
        
        # Create a sheet with documentation
        docs_sheet = self.wb.create_sheet("Documentation")
        docs_sheet.cell(row=1, column=1, value="Financial Forecaster Documentation")
        docs_sheet.cell(row=1, column=1).font = Font(bold=True, size=14)
        
        docs = [
            ["Overview", "This workbook helps forecast financial transactions and account balances based on recurring transactions."],
            ["Sheets", ""],
            ["TransactionTypes", "Reference table for transaction types and their effects on account balances."],
            ["Debts", "Information about credit cards including interest rates and payment dates."],
            ["RecurringTransactions", "Configure recurring transactions with frequencies and end conditions."],
            ["Forecast", "View of projected transactions and account balances over time."],
            ["", ""],
            ["Usage", ""],
            ["1.", "Enter current account balances in the Forecast sheet (row 2)."],
            ["2.", "Configure your credit cards in the Debts sheet."],
            ["3.", "Set up recurring transactions in the RecurringTransactions sheet."],
            ["4.", "Run the Python script with --update flag to refresh the forecast."],
            ["", ""],
            ["Transaction Types", "Each transaction type affects account balances differently:"],
            ["- Purchase on Credit Card", "Increases the credit card balance (you owe more)"],
            ["- Payment to Credit Card", "Decreases the credit card balance (you owe less)"],
            ["- Deposit to Checking", "Increases the checking account balance"],
            ["- Withdrawal from Checking", "Decreases the checking account balance"],
        ]
        
        for row_idx, (col1, col2) in enumerate(docs, 1):
            docs_sheet.cell(row=row_idx, column=1, value=col1)
            docs_sheet.cell(row=row_idx, column=2, value=col2)
            
            if row_idx in [1, 2, 8, 14]:  # Section headers
                docs_sheet.cell(row=row_idx, column=1).font = Font(bold=True)
        
        # Set column widths
        docs_sheet.column_dimensions['A'].width = 20
        docs_sheet.column_dimensions['B'].width = 80
        
        return self.wb
    
    def save(self, filename="Financial_Forecaster.xlsx"):
        """Save the workbook to a file"""
        self.wb.save(filename)
        return filename