#!/usr/bin/env python3
"""
Financial Forecaster - Main Script
=================================

A tool to create and manage financial forecasts with recurring transactions.
"""

import os
import argparse
from datetime import datetime, timedelta

def main():
    """Main entry point for the Financial Forecaster application"""
    parser = argparse.ArgumentParser(description="Financial Forecaster Tool")
    parser.add_argument("--create", action="store_true", help="Create a new financial forecaster workbook")
    parser.add_argument("--update", type=str, help="Update an existing workbook forecast")
    parser.add_argument("--output", type=str, default="Financial_Forecaster.xlsx", 
                        help="Output filename (default: Financial_Forecaster.xlsx)")
    parser.add_argument("--forecast-days", type=int, default=180, 
                        help="Number of days to forecast (default: 180)")
    
    args = parser.parse_args()
    
    if args.create:
        # Create new workbook
        print(f"Creating new financial forecaster workbook: {args.output}")
        from financial_forecaster_core import FinancialForecaster
        
        forecaster = FinancialForecaster()
        workbook = forecaster.create_workbook()
        filename = forecaster.save(args.output)
        print(f"Financial forecaster workbook created: {filename}")
        
    elif args.update:
        # Update existing workbook
        if not os.path.exists(args.update):
            print(f"Error: File {args.update} not found.")
            return
            
        print(f"Updating forecast in: {args.update}")
        from excel_updater import populate_forecast_from_recurring
        
        populate_forecast_from_recurring(args.update, forecast_days=args.forecast_days)
        print(f"Forecast updated: {args.update}")
        
    else:
        # No action specified, create new workbook
        print(f"Creating new financial forecaster workbook: {args.output}")
        from financial_forecaster_core import FinancialForecaster
        
        forecaster = FinancialForecaster()
        workbook = forecaster.create_workbook()
        filename = forecaster.save(args.output)
        print(f"Financial forecaster workbook created: {filename}")
        
    print("\nTo use the forecaster:")
    print("1. Open the Excel file")
    print("2. Fill in your actual account balances in the 'Forecast' sheet (row 2)")
    print("3. Configure your credit cards in the 'Debts' sheet")
    print("4. Set up your recurring transactions in the 'RecurringTransactions' sheet")
    print("5. Run this script with --update to refresh the forecast based on your settings")

if __name__ == "__main__":
    main()