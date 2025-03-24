# Financial Forecaster

A Python-based tool to create and manage financial forecasts with recurring transactions and account balance projections.

## Features

- Track multiple bank and credit card accounts
- Configure recurring transactions with various frequency options
- Calculate account balances over time
- Factor in credit card interest and minimum payments
- Visualize your financial future

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/awingo90/financial_forecaster.git
   cd financial-forecaster
   ```

2. Create a virtual environment (recommended):
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

## Usage

### Creating a New Forecast Workbook

```
python financial_forecaster.py --create --output MyForecast.xlsx
```

### Updating an Existing Forecast

```
python financial_forecaster.py --update MyForecast.xlsx --forecast-days 365
```

### Using the Excel File

1. Open the Excel file
2. Fill in your actual account balances in the 'Forecast' sheet (row 2)
3. Configure your credit cards in the 'Debts' sheet
4. Set up your recurring transactions in the 'RecurringTransactions' sheet
5. Run the update script to refresh the forecast

## Project Structure

- `financial_forecaster.py` - Main entry point
- `financial_forecaster_core.py` - Core Excel workbook creation
- `transaction_generator.py` - Recurring transaction generation logic
- `excel_updater.py` - Functions for updating Excel with new forecasts

## Customization Options

### Recurring Transaction Types

- **Frequency**: Daily, Weekly, Bi-Weekly, Monthly, Quarterly, Semi-Annual, Annual
- **End Conditions**: Specific date, Number of occurrences, Indefinite
- **Day Selection**: Day of month for monthly, Day of week for weekly/bi-weekly

### Credit Card Settings

- Interest rates
- Statement close dates
- Payment due dates
- Minimum payment calculations

## Example Workflow

1. Set up your accounts and starting balances
2. Add your recurring income transactions (paychecks, etc.)
3. Add your recurring expense transactions (rent, utilities, etc.)
4. Add your recurring credit card payments
5. Run the forecast to see your projected balances
6. Adjust your financial plan as needed

## Visualization

The tool can generate visualizations of your account balances over time:

```
python excel_updater.py MyForecast.xlsx --visualize my_forecast_chart.png
```

## License

MIT