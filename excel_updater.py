#!/usr/bin/env python3
"""
Excel Updater Module
===================

Functions for updating the Excel workbook with generated transactions and balances.
"""

import pandas as pd
import numpy as np
import openpyxl
from openpyxl.styles import Font, PatternFill, Border, Side, Alignment
from openpyxl.utils import get_column_letter
from datetime import datetime, timedelta
import calendar
import logging
from transaction_generator import (
    generate_recurring_transactions,
    calculate_account_balances,
    calculate_credit_card_interest,
    add_minimum_payments
)

# Set up logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def _get_values_from_range(sheet, start_cell, end_cell):
    """Extract values from a range of cells"""
    values = []
    for row in sheet[start_cell:end_cell]:
        row_values = []
        for cell in row:
            row_values.append(cell.value)
        values.append(row_values)
    return values

def populate_forecast_from_recurring(excel_file, forecast_days=180, preserve_manual=True):
    """
    Update the forecast sheet based on recurring transactions
    
    Args:
        excel_file: Path to the Excel workbook
        forecast_days: Number of days to forecast
        preserve_manual: Whether to preserve manually added transactions
    
    Returns:
        str: Path to the updated Excel file
    """
    logger.info(f"Updating forecast in {excel_file} for {forecast_days} days")
    
    # Load workbook
    wb = openpyxl.load_workbook(excel_file)
    
    # Read all the necessary sheets
    transaction_types_sheet = wb["TransactionTypes"]
    debts_sheet = wb["Debts"]
    recurring_sheet = wb["RecurringTransactions"]
    forecast_sheet = wb["Forecast"]
    
    # Extract transaction types data
    transaction_types_data = _get_values_from_range(
        transaction_types_sheet, 
        transaction_types_sheet.cell(row=1, column=1),
        transaction_types_sheet.cell(
            row=transaction_types_sheet.max_row, 
            column=transaction_types_sheet.max_column
        )
    )
    
    # Extract debt data
    debt_headers = [cell.value for cell in debts_sheet[1]]
    debt_data = []
    
    for row in range(2, debts_sheet.max_row + 1):
        if debts_sheet.cell(row=row, column=1).value:  # Skip empty rows
            debt_row = {}
            for col, header in enumerate(debt_headers, 1):
                debt_row[header] = debts_sheet.cell(row=row, column=col).value
            debt_data.append(debt_row)
    
    # Extract recurring transactions data
    recurring_headers = [cell.value for cell in recurring_sheet[1]]
    recurring_data = []
    
    for row in range(2, recurring_sheet.max_row + 1):
        if recurring_sheet.cell(row=row, column=1).value:  # Skip empty rows
            recurring_row = {}
            for col, header in enumerate(recurring_headers, 1):
                recurring_row[header] = recurring_sheet.cell(row=row, column=col).value
            recurring_data.append(recurring_row)
    
    # Extract current balances from the forecast sheet
    forecast_headers = [cell.value for cell in forecast_sheet[1]]
    transaction_cols = 6  # Number of transaction detail columns
    
    # Get account names
    account_names = [header for header in forecast_headers[transaction_cols:] if header]
    
    # Get initial balances from the first transaction row
    initial_balances = {}
    for col_idx, account in enumerate(account_names, 1):
        cell_value = forecast_sheet.cell(row=2, column=transaction_cols + col_idx).value
        initial_balances[account] = cell_value if cell_value is not None else 0
    
    # Collect any manual transactions if preserving them
    manual_transactions = []
    if preserve_manual:
        for row in range(3, forecast_sheet.max_row + 1):
            cell_value = forecast_sheet.cell(row=row, column=1).value
            if cell_value:  # If there's a date, assume it's a valid transaction
                manual_txn = {}
                for col_idx, header in enumerate(forecast_headers[:transaction_cols], 1):
                    if header:
                        manual_txn[header] = forecast_sheet.cell(row=row, column=col_idx).value
                
                # Only add if it has basic transaction details
                if manual_txn.get('Date') and manual_txn.get('Transaction'):
                    manual_txn['IsManual'] = True
                    manual_transactions.append(manual_txn)
    
    # Set forecast period
    start_date = datetime.now()
    end_date = start_date + timedelta(days=forecast_days)
    
    # Generate recurring transactions
    transactions = generate_recurring_transactions(start_date, end_date, recurring_data)
    
    # Merge with manual transactions if needed
    if manual_transactions:
        transactions.extend(manual_transactions)
        transactions.sort(key=lambda x: x['Date'])
    
    # Calculate balances for all transactions
    transactions_with_balances = calculate_account_balances(
        transactions, initial_balances, transaction_types_data, debt_data
    )
    
    # Add interest charges
    transactions_with_interest = calculate_credit_card_interest(
        transactions_with_balances, debt_data
    )
    
    # Add minimum payments where needed
    final_transactions = add_minimum_payments(
        transactions_with_interest, debt_data
    )
    
    # Recalculate all balances again now that we have interest and payments
    final_transactions_with_balances = calculate_account_balances(
        final_transactions, initial_balances, transaction_types_data, debt_data
    )
    
    # Clear existing transactions in the forecast sheet (preserve initial balances)
    for row in range(3, forecast_sheet.max_row + 1):
        for col in range(1, forecast_sheet.max_column + 1):
            forecast_sheet.cell(row=row, column=col).value = None
    
    # Write the transactions to the forecast sheet
    date_format = 'mm/dd/yyyy'
    currency_format = '_($* #,##0.00_);_($* (#,##0.00);_($* "-"??_);_(@_)'
    
    for row_idx, txn in enumerate(final_transactions_with_balances, 3):
        # Transaction details
        forecast_sheet.cell(row=row_idx, column=1).value = txn['Date']
        forecast_sheet.cell(row=row_idx, column=1).number_format = date_format
        
        forecast_sheet.cell(row=row_idx, column=2).value = txn['Transaction']
        forecast_sheet.cell(row=row_idx, column=3).value = txn['Type']
        forecast_sheet.cell(row=row_idx, column=4).value = txn['From']
        forecast_sheet.cell(row=row_idx, column=5).value = txn['To']
        
        forecast_sheet.cell(row=row_idx, column=6).value = txn['Amount']
        forecast_sheet.cell(row=row_idx, column=6).number_format = currency_format
        
        # Account balances
        for col_idx, account in enumerate(account_names, 1):
            if account in txn:
                forecast_sheet.cell(row=row_idx, column=transaction_cols + col_idx).value = txn[account]
                forecast_sheet.cell(row=row_idx, column=transaction_cols + col_idx).number_format = currency_format
    
    # Add formatting
    # Alternate row colors
    light_gray_fill = PatternFill(start_color="F5F5F5", end_color="F5F5F5", fill_type="solid")
    for row in range(3, len(final_transactions_with_balances) + 3):
        if row % 2 == 1:  # Odd rows (3, 5, 7, etc.)
            for col in range(1, len(forecast_headers) + 1):
                forecast_sheet.cell(row=row, column=col).fill = light_gray_fill
    
    # Highlight transaction types differently
    payment_fill = PatternFill(start_color="E3F2FD", end_color="E3F2FD", fill_type="solid")
    expense_fill = PatternFill(start_color="FFEBEE", end_color="FFEBEE", fill_type="solid")
    income_fill = PatternFill(start_color="E8F5E9", end_color="E8F5E9", fill_type="solid")
    interest_fill = PatternFill(start_color="FFF3E0", end_color="FFF3E0", fill_type="solid")
    
    for row in range(3, len(final_transactions_with_balances) + 3):
        txn_type = forecast_sheet.cell(row=row, column=3).value
        if txn_type and "Payment" in txn_type:
            forecast_sheet.cell(row=row, column=3).fill = payment_fill
        elif txn_type and txn_type in ["Purchase", "Debit Card Purchase"]:
            forecast_sheet.cell(row=row, column=3).fill = expense_fill
        elif txn_type and txn_type in ["Deposit", "Mobile Deposit", "Interest Earned"]:
            forecast_sheet.cell(row=row, column=3).fill = income_fill
        elif txn_type and "Interest" in txn_type:
            forecast_sheet.cell(row=row, column=3).fill = interest_fill
    
    # Save the workbook
    wb.save(excel_file)
    logger.info(f"Updated forecast with {len(final_transactions_with_balances)} transactions")
    
    return excel_file


def export_transactions_to_csv(excel_file, output_csv):
    """
    Export the forecast transactions to a CSV file
    
    Args:
        excel_file: Path to the Excel workbook
        output_csv: Path for the output CSV file
    
    Returns:
        str: Path to the created CSV file
    """
    # Read the forecast sheet
    df = pd.read_excel(excel_file, sheet_name="Forecast")
    
    # Export to CSV
    df.to_csv(output_csv, index=False)
    logger.info(f"Exported transactions to {output_csv}")
    
    return output_csv


def generate_visualization(excel_file, output_image=None):
    """
    Generate a cash flow visualization from the forecast data
    
    Args:
        excel_file: Path to the Excel workbook
        output_image: Optional path for the output image file
    
    Returns:
        str: Path to the created image file (if output_image provided)
    """
    try:
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
        
        # Read the forecast data
        df = pd.read_excel(excel_file, sheet_name="Forecast")
        
        # Convert date column to datetime
        df['Date'] = pd.to_datetime(df['Date'])
        
        # Get account columns (assuming transaction details are in first 6 columns)
        account_columns = df.columns[6:]
        
        # Create plot
        plt.figure(figsize=(12, 8))
        
        # Plot each account balance over time
        for account in account_columns:
            if df[account].notna().any():  # Only plot accounts with data
                plt.plot(df['Date'], df[account], label=account)
        
        # Format the plot
        plt.title('Account Balance Forecast')
        plt.xlabel('Date')
        plt.ylabel('Balance ($)')
        plt.grid(True, linestyle='--', alpha=0.7)
        plt.legend()
        
        # Format x-axis to show dates nicely
        plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%m/%d/%Y'))
        plt.gca().xaxis.set_major_locator(mdates.WeekdayLocator(interval=2))
        plt.gcf().autofmt_xdate()
        
        # Add zero line to easily spot negative balances
        plt.axhline(y=0, color='r', linestyle='-', alpha=0.3)
        
        # Save or show the plot
        if output_image:
            plt.savefig(output_image, dpi=300, bbox_inches='tight')
            logger.info(f"Saved visualization to {output_image}")
            return output_image
        else:
            plt.show()
            
    except ImportError:
        logger.warning("Matplotlib not installed. Cannot generate visualization.")
        return None


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Financial Forecaster Excel Updater")
    parser.add_argument("excel_file", help="Path to the Excel workbook")
    parser.add_argument("--days", type=int, default=180, help="Number of days to forecast")
    parser.add_argument("--no-preserve", action="store_true", help="Don't preserve manual transactions")
    parser.add_argument("--export-csv", help="Export transactions to CSV file")
    parser.add_argument("--visualize", help="Generate and save visualization to image file")
    
    args = parser.parse_args()
    
    # Update the forecast
    populate_forecast_from_recurring(
        args.excel_file, 
        forecast_days=args.days,
        preserve_manual=not args.no_preserve
    )
    
    # Export to CSV if requested
    if args.export_csv:
        export_transactions_to_csv(args.excel_file, args.export_csv)
    
    # Generate visualization if requested
    if args.visualize:
        generate_visualization(args.excel_file, args.visualize)