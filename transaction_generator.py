#!/usr/bin/env python3
"""
Transaction Generator Module
===========================

Functions for generating recurring transactions and calculating account balances.
"""

from datetime import datetime, timedelta
import calendar
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_next_date_monthly(current_date, day_of_month):
    """
    Get the next date for a monthly recurring transaction
    
    Args:
        current_date: The current date
        day_of_month: The day of the month for the transaction
    
    Returns:
        datetime: The next occurrence date
    """
    # Get year and month for next month
    year = current_date.year
    month = current_date.month + 1
    
    # Handle year rollover
    if month > 12:
        month = 1
        year += 1
    
    # Ensure valid day (handle month end cases)
    last_day = calendar.monthrange(year, month)[1]
    day = min(int(day_of_month), last_day)
    
    return datetime(year, month, day)


def get_next_date_by_weekday(current_date, weekday, days_interval):
    """
    Get the next date for a weekly/bi-weekly recurring transaction
    
    Args:
        current_date: The current date
        weekday: The day of the week (Mon, Tue, etc.)
        days_interval: Number of days between occurrences (7 for weekly, 14 for bi-weekly)
    
    Returns:
        datetime: The next occurrence date
    """
    # Map day names to weekday numbers (0 = Monday, 6 = Sunday)
    day_map = {'mon': 0, 'tue': 1, 'wed': 2, 'thu': 3, 'fri': 4, 'sat': 5, 'sun': 6}
    
    # Get target weekday number
    target_weekday = day_map.get(weekday.lower()[:3], 0)
    
    # Calculate days to add to get to the next occurrence
    days_to_add = (target_weekday - current_date.weekday()) % 7
    
    # If we're already on the right weekday but need to move forward
    if days_to_add == 0 and days_interval > 0:
        days_to_add = days_interval
    
    # For bi-weekly, add another week
    if days_interval == 14 and days_to_add < 7:
        days_to_add += 7
    
    return current_date + timedelta(days=days_to_add)


def generate_recurring_transactions(start_date, end_date, recurring_data):
    """
    Generate all instances of recurring transactions between start and end dates
    
    Args:
        start_date: Beginning date for the forecast
        end_date: Ending date for the forecast
        recurring_data: List of recurring transaction configurations
    
    Returns:
        list: All transactions in the date range
    """
    logger.info(f"Generating recurring transactions from {start_date} to {end_date}")
    
    all_transactions = []
    
    for recurring in recurring_data:
        # Skip inactive transactions
        if not recurring.get('Active') or str(recurring.get('Active')).lower() != 'yes':
            continue
        
        logger.debug(f"Processing recurring transaction: {recurring.get('Transaction')}")
        
        current_date = recurring.get('Start Date')
        if not current_date:
            current_date = start_date
            
        # Skip transactions that start after our end date
        if current_date > end_date:
            continue
            
        frequency = str(recurring.get('Frequency', '')).lower()
        end_type = str(recurring.get('End Type', '')).lower()
        
        # Define frequency in days for simple frequencies
        if frequency == 'daily':
            days_interval = 1
        elif frequency == 'weekly':
            days_interval = 7
        elif frequency == 'bi-weekly':
            days_interval = 14
        elif frequency == 'quarterly':
            days_interval = 91  # Approximation
        elif frequency == 'semi-annual':
            days_interval = 182  # Approximation
        elif frequency == 'annual':
            days_interval = 365  # Approximation
        else:
            # Default to monthly
            days_interval = 30  # Will be handled specially for monthly
        
        # Handle count-based end condition
        max_count = float('inf')
        if end_type == 'count' and recurring.get('End Date/Count'):
            try:
                max_count = int(recurring.get('End Date/Count'))
            except (ValueError, TypeError):
                logger.warning(f"Invalid count value for {recurring.get('Transaction')}")
                max_count = float('inf')
        
        # Handle date-based end condition
        max_date = datetime(2099, 12, 31)  # Far future default
        if end_type == 'date' and recurring.get('End Date/Count'):
            try:
                if isinstance(recurring.get('End Date/Count'), datetime):
                    max_date = recurring.get('End Date/Count')
                else:
                    # Try to parse string date if needed
                    max_date = datetime.strptime(str(recurring.get('End Date/Count')), '%Y-%m-%d')
            except (ValueError, TypeError):
                logger.warning(f"Invalid end date for {recurring.get('Transaction')}")
                max_date = datetime(2099, 12, 31)
        
        # Generate all occurrences
        count = 0
        
        while current_date <= end_date and current_date <= max_date and count < max_count:
            # Special handling for monthly transactions with specified day
            if frequency == 'monthly' and recurring.get('Monthly Day'):
                try:
                    day = int(recurring.get('Monthly Day'))
                    # Only adjust the day if this is not the first occurrence
                    if count > 0 or current_date < start_date:
                        # Set to the specified day in current month
                        year, month = current_date.year, current_date.month
                        last_day = calendar.monthrange(year, month)[1]
                        day = min(day, last_day)
                        current_date = datetime(year, month, day)
                except (ValueError, TypeError):
                    logger.warning(f"Invalid monthly day for {recurring.get('Transaction')}")
            
            # Special handling for weekly transactions with specified day
            if (frequency == 'weekly' or frequency == 'bi-weekly') and recurring.get('Weekly Day'):
                # Only adjust the weekday if this is not the first occurrence
                if count > 0 or current_date < start_date:
                    try:
                        current_date = get_next_date_by_weekday(
                            current_date - timedelta(days=1),  # Back up one day to ensure proper next weekday
                            recurring.get('Weekly Day'),
                            days_interval
                        )
                    except Exception as e:
                        logger.warning(f"Error adjusting weekly day: {e}")
            
            # Only add the transaction if it's within our date range
            if start_date <= current_date <= end_date and current_date <= max_date:
                transaction = {
                    'Date': current_date,
                    'Transaction': recurring.get('Transaction'),
                    'Type': recurring.get('Type'),
                    'From': recurring.get('From'),
                    'To': recurring.get('To'),
                    'Amount': recurring.get('Amount', 0)
                }
                all_transactions.append(transaction)
                logger.debug(f"Added transaction: {transaction['Transaction']} on {transaction['Date']}")
            
            # Move to next occurrence
            if frequency == 'monthly':
                if recurring.get('Monthly Day'):
                    current_date = get_next_date_monthly(current_date, recurring.get('Monthly Day'))
                else:
                    # If no day specified, just add a month (approximate)
                    current_date = current_date + timedelta(days=30)
            elif frequency in ['weekly', 'bi-weekly'] and recurring.get('Weekly Day'):
                current_date = get_next_date_by_weekday(current_date, recurring.get('Weekly Day'), days_interval)
            else:
                # For all other frequencies, just add the days interval
                current_date = current_date + timedelta(days=days_interval)
            
            count += 1
    
    # Sort all transactions by date
    all_transactions.sort(key=lambda x: x['Date'])
    
    logger.info(f"Generated {len(all_transactions)} transactions")
    return all_transactions


def calculate_account_balances(transactions, initial_balances, transaction_types_data, debt_data=None):
    """
    Calculate progressive account balances for all transactions
    
    Args:
        transactions: List of transactions
        initial_balances: Dictionary of initial account balances
        transaction_types_data: Transaction types reference data
        debt_data: Optional credit card data for interest calculations
    
    Returns:
        list: Transactions with updated balances
    """
    logger.info("Calculating account balances")
    
    # Initialize results with initial balances
    balances = initial_balances.copy()
    results = []
    
    # Create a lookup for transaction type effects
    transaction_effects = {}
    
    # Skip header if present
    start_idx = 0
    if isinstance(transaction_types_data[0], list) and transaction_types_data[0][0] == "Type":
        start_idx = 1
    
    for row in transaction_types_data[start_idx:]:
        transaction_effects[row[0]] = {
            'Balance Effect': row[2],
            'Account Type': row[4]
        }
    
    # Process each transaction
    for txn in transactions:
        # Copy current balances
        current_balances = balances.copy()
        
        # Get transaction details
        txn_type = txn['Type']
        txn_from = txn['From']
        txn_to = txn['To']
        
        # Handle different amount formats (Excel sometimes returns different types)
        try:
            txn_amount = float(txn['Amount'])
        except (ValueError, TypeError):
            logger.warning(f"Invalid amount for transaction: {txn}")
            txn_amount = 0
        
        # Look up how this transaction affects balances
        if txn_type in transaction_effects:
            effect = transaction_effects[txn_type]['Balance Effect']
            account_type = transaction_effects[txn_type]['Account Type']
            
            # Apply transaction effects
            if txn_from in balances and txn_from != 'External':
                # For debit accounts, decreases mean money leaves
                # For credit accounts, decreases mean balance reduces (payment)
                if account_type == 'Debit' and effect in ['Decreases', '+/-']:
                    balances[txn_from] -= txn_amount
                elif account_type == 'Credit' and effect == 'Decreases':
                    balances[txn_from] -= txn_amount
                elif account_type == 'Credit' and effect == 'Increases':
                    balances[txn_from] += txn_amount
            
            if txn_to in balances and txn_to != 'External':
                # For debit accounts, increases mean money arrives
                # For credit accounts, increases mean balance grows (purchase)
                if account_type == 'Debit' and effect in ['Increases', '+/-']:
                    balances[txn_to] += txn_amount
                elif account_type == 'Credit' and effect == 'Increases':
                    balances[txn_to] += txn_amount
                elif account_type == 'Credit' and effect == 'Decreases':
                    balances[txn_to] -= txn_amount
        
        # For Balance Transfers, handle specially
        if txn_type == 'Balance Transfer':
            if txn_from in balances and txn_from != 'External':
                balances[txn_from] -= txn_amount
            if txn_to in balances and txn_to != 'External':
                balances[txn_to] += txn_amount
        
        # Store the results
        result = {
            'Date': txn['Date'],
            'Transaction': txn['Transaction'],
            'Type': txn_type,
            'From': txn_from,
            'To': txn_to,
            'Amount': txn_amount
        }
        
        # Add the balances
        for account, balance in balances.items():
            result[account] = balance
        
        results.append(result)
    
    logger.info("Balance calculation complete")
    return results


def calculate_credit_card_interest(transactions_with_balances, debt_data):
    """
    Calculate and add interest transactions for credit cards
    
    Args:
        transactions_with_balances: Transactions with calculated balances
        debt_data: Credit card configuration data
    
    Returns:
        list: Transactions with interest charges added
    """
    logger.info("Calculating credit card interest")
    
    results = transactions_with_balances.copy()
    
    # Group transactions by month
    monthly_transactions = {}
    for txn in transactions_with_balances:
        date = txn['Date']
        month_key = (date.year, date.month)
        if month_key not in monthly_transactions:
            monthly_transactions[month_key] = []
        monthly_transactions[month_key].append(txn)
    
    # Process each month for each credit card
    interest_transactions = []
    for month_key, transactions in monthly_transactions.items():
        year, month = month_key
        
        # Sort transactions by date
        sorted_txns = sorted(transactions, key=lambda x: x['Date'])
        
        # For each credit card account
        for debt in debt_data:
            account = debt['Account']
            
            # Skip if account isn't in the transactions
            if not any(account in txn for txn in sorted_txns):
                continue
            
            # Get interest rate and statement close day
            try:
                interest_rate = float(debt['Interest Rate'])
                statement_close_day = int(debt['Statement Close Day'])
            except (ValueError, TypeError, KeyError):
                logger.warning(f"Missing or invalid interest data for {account}")
                continue
            
            # Find the last transaction of the month for this account
            last_balance = None
            for txn in reversed(sorted_txns):
                if account in txn and txn[account] is not None:
                    last_balance = txn[account]
                    break
            
            # Calculate interest if balance is positive (debt)
            if last_balance is not None and last_balance > 0:
                # Calculate interest (simplified: monthly rate * balance)
                monthly_rate = interest_rate / 12
                interest_amount = last_balance * monthly_rate
                
                # Create interest transaction on statement close date
                last_day = calendar.monthrange(year, month)[1]
                interest_day = min(statement_close_day, last_day)
                
                try:
                    interest_date = datetime(year, month, interest_day)
                    
                    # Don't add interest for future months
                    if interest_date > datetime.now() + timedelta(days=365):
                        continue
                    
                    interest_txn = {
                        'Date': interest_date,
                        'Transaction': f'Interest Charge - {account}',
                        'Type': 'Interest',
                        'From': None,
                        'To': account,
                        'Amount': interest_amount
                    }
                    
                    interest_transactions.append(interest_txn)
                    logger.debug(f"Added interest charge of {interest_amount:.2f} to {account} on {interest_date}")
                except Exception as e:
                    logger.error(f"Error creating interest transaction: {e}")
    
    # Add interest transactions and re-sort
    results.extend(interest_transactions)
    results.sort(key=lambda x: x['Date'])
    
    # Recalculate balances with interest included
    # This would ideally reuse the balance calculation logic
    
    logger.info(f"Added {len(interest_transactions)} interest transactions")
    return results


def add_minimum_payments(transactions_with_balances, debt_data):
    """
    Add minimum payment transactions for credit cards
    
    Args:
        transactions_with_balances: Transactions with calculated balances
        debt_data: Credit card configuration data
    
    Returns:
        list: Transactions with minimum payments added
    """
    logger.info("Adding minimum credit card payments")
    
    results = transactions_with_balances.copy()
    
    # Group transactions by month
    monthly_transactions = {}
    for txn in transactions_with_balances:
        date = txn['Date']
        month_key = (date.year, date.month)
        if month_key not in monthly_transactions:
            monthly_transactions[month_key] = []
        monthly_transactions[month_key].append(txn)
    
    # Process each month for each credit card
    min_payment_transactions = []
    
    for month_key, transactions in monthly_transactions.items():
        year, month = month_key
        
        # Skip past months
        if datetime(year, month, 1) < datetime.now().replace(day=1):
            continue
        
        # Sort transactions by date
        sorted_txns = sorted(transactions, key=lambda x: x['Date'])
        
        # For each credit card account
        for debt in debt_data:
            account = debt['Account']
            
            # Skip if account isn't in the transactions
            if not any(account in txn for txn in sorted_txns):
                continue
            
            # Get payment parameters
            try:
                min_payment_pct = float(debt['Min Payment %'])
                min_payment_fixed = float(debt['Min Payment Fixed'])
                payment_due_day = int(debt['Payment Due Day'])
            except (ValueError, TypeError, KeyError):
                logger.warning(f"Missing or invalid payment data for {account}")
                continue
            
            # Find the balance at statement close
            statement_close_day = int(debt['Statement Close Day'])
            statement_close_date = None
            statement_balance = None
            
            # Try to find the balance on statement close date
            last_day = calendar.monthrange(year, month)[1]
            close_day = min(statement_close_day, last_day)
            statement_close_date = datetime(year, month, close_day)
            
            # Get the balance on or after statement close
            for txn in sorted_txns:
                if account in txn and txn['Date'] >= statement_close_date:
                    statement_balance = txn[account]
                    break
            
            # If no transaction found on statement close date, use last transaction
            if statement_balance is None:
                for txn in reversed(sorted_txns):
                    if account in txn:
                        statement_balance = txn[account]
                        break
            
            # Calculate minimum payment if balance is positive (debt)
            if statement_balance is not None and statement_balance > 0:
                # Calculate based on percentage or fixed amount, whichever is higher
                pct_payment = statement_balance * min_payment_pct
                min_payment = max(pct_payment, min_payment_fixed)
                
                # Cap at the statement balance (don't overpay)
                min_payment = min(min_payment, statement_balance)
                
                # Create payment transaction on payment due date
                # Payment is due in the next month
                next_month = month + 1
                next_year = year
                if next_month > 12:
                    next_month = 1
                    next_year += 1
                
                last_day_next = calendar.monthrange(next_year, next_month)[1]
                payment_day = min(payment_due_day, last_day_next)
                
                try:
                    payment_date = datetime(next_year, next_month, payment_day)
                    
                    # Check if there's already a payment to this account around the due date
                    payment_window_start = payment_date - timedelta(days=5)
                    payment_window_end = payment_date + timedelta(days=5)
                    
                    existing_payment = False
                    for txn in transactions_with_balances:
                        if (txn['Type'] == 'Payment' and 
                            txn['To'] == account and
                            payment_window_start <= txn['Date'] <= payment_window_end):
                            existing_payment = True
                            break
                    
                    # Only add if there's no existing payment
                    if not existing_payment:
                        payment_txn = {
                            'Date': payment_date,
                            'Transaction': f'Minimum Payment - {account}',
                            'Type': 'Payment',
                            'From': 'Checking Account',  # Assume from checking
                            'To': account,
                            'Amount': min_payment
                        }
                        
                        min_payment_transactions.append(payment_txn)
                        logger.debug(f"Added minimum payment of {min_payment:.2f} to {account} on {payment_date}")
                except Exception as e:
                    logger.error(f"Error creating minimum payment transaction: {e}")
    
    # Add payment transactions and re-sort
    results.extend(min_payment_transactions)
    results.sort(key=lambda x: x['Date'])
    
    logger.info(f"Added {len(min_payment_transactions)} minimum payment transactions")
    return results