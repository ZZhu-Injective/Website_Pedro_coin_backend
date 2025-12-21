import os
import pandas as pd
from openpyxl import load_workbook
from datetime import datetime

class TalentDatabase:
    def __init__(self, excel_file='Atalent_submissions.xlsx'):
        self.file_path = os.path.join(excel_file)
    
    def load_data(self) -> pd.DataFrame:
        try:
            if not os.path.exists(self.file_path):
                raise FileNotFoundError(f"Database file not found at {self.file_path}")
            
            # Load workbook with openpyxl to inspect it
            wb = load_workbook(self.file_path, data_only=True)  # data_only gets calculated values
            ws = wb.active
            
            # Read the Excel file with better handling for dates
            df = pd.read_excel(
                self.file_path,
                sheet_name=ws.title,
                header=0,
                engine='openpyxl',
                dtype=str  # Read everything as string first to handle mixed types
            )
            
            expected_columns = [
                "Name", "Role", "Injective Role", "Experience", "Education", 
                "Location", "Availability", "Monthly Rate", "Skills", "Languages",
                "Discord", "Email", "Phone", "Telegram", "X", "Github",
                "Wallet Address", "Wallet Type", "NFT Holdings", "Token Holdings",
                "Portfolio", "CV", "Image url", "Bio", "Submission date", "Status"
            ]
            
            # Add missing columns
            for col in expected_columns:
                if col not in df.columns:
                    df[col] = None
            
            # Convert 'Submission date' properly
            if 'Submission date' in df.columns:
                df['Submission date'] = self._parse_dates(df['Submission date'])
            
            # Clean up the data - ensure all columns are strings
            for col in df.columns:
                if df[col].dtype == 'object':
                    df[col] = df[col].astype(str).replace('nan', '').replace('None', '')
            
            return df
            
        except Exception as e:
            print(f"Error loading database: {e}")
            import traceback
            traceback.print_exc()
            return pd.DataFrame()
    
    def _parse_dates(self, date_series):
        """Helper function to parse dates from various formats"""
        def parse_single_date(date_val):
            if pd.isna(date_val) or date_val == '' or date_val == 'nan' or date_val == 'None':
                return pd.NaT
            
            # Try to parse as string first
            if isinstance(date_val, str):
                # Handle Excel serial numbers (e.g., "45810")
                if date_val.isdigit():
                    try:
                        # Excel serial number to datetime (Excel's epoch is 1899-12-30)
                        excel_serial = float(date_val)
                        # Adjust for Excel's leap year bug (Excel thinks 1900 was a leap year)
                        if excel_serial > 60:
                            excel_serial -= 1
                        base_date = datetime(1899, 12, 30)
                        return base_date + pd.Timedelta(days=excel_serial)
                    except:
                        pass
                
                # Try parsing as ISO format
                try:
                    return pd.to_datetime(date_val, format='ISO8601')
                except:
                    pass
                
                # Try mixed formats
                try:
                    return pd.to_datetime(date_val, dayfirst=True, errors='coerce')
                except:
                    pass
            
            # If it's already a datetime or numeric type
            try:
                return pd.to_datetime(date_val, errors='coerce')
            except:
                return pd.NaT
        
        return date_series.apply(parse_single_date)
    
    def get_by_wallet(self, wallet_address: str) -> pd.DataFrame:
        df = self.load_data()
        if df.empty:
            print("DataFrame is empty after loading")
            return pd.DataFrame()
        
        print(f"DataFrame shape: {df.shape}")
        print(f"Columns: {df.columns.tolist()}")
        
        if 'Wallet Address' in df.columns:
            print(f"Sample wallet addresses: {df['Wallet Address'].head().tolist()}")
            # Handle NaN values in wallet addresses
            df['Wallet Address'] = df['Wallet Address'].fillna('').astype(str)
            result = df[df['Wallet Address'].str.lower() == wallet_address.lower()].copy()
            print(f"Found {len(result)} records for wallet: {wallet_address}")
            return result
        
        print("'Wallet Address' column not found in DataFrame")
        return pd.DataFrame()
    
    def get_talent_by_wallet(self, wallet_address: str) -> dict:
        try:
            wallet_data = self.get_by_wallet(wallet_address)
            
            if wallet_data.empty:
                print(f"No data found for wallet: {wallet_address}")
                return {
                    "info": "no",
                    "message": "No submissions found for this wallet address"
                }
            
            # Convert to dictionary records
            wallet_data = wallet_data.fillna('')
            submissions = wallet_data.to_dict('records')
            
            # Clean up the records for JSON serialization
            for record in submissions:
                for key, value in record.items():
                    if pd.isna(value):
                        record[key] = None
                    elif isinstance(value, (pd.Timestamp, datetime)):
                        record[key] = value.isoformat() if not pd.isna(value) else None
            
            if len(submissions) == 1:
                return {
                    "info": "yes",
                    "message": "Single submission found",
                    **submissions[0]
                }
            
            return {
                "info": "yes",
                "message": f"{len(submissions)} submissions found",
                "count": len(submissions),
                "wallet_address": wallet_address,
                "submissions": submissions
            }
            
        except Exception as e:
            print(f"Error in get_talent_by_wallet: {e}")
            import traceback
            traceback.print_exc()
            return {
                "info": "no",
                "message": f"Error processing request: {str(e)}"
            }