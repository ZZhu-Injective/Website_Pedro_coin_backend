import os
import pandas as pd
from openpyxl import load_workbook

#Checking Talent to retrieve it based on the walletaddress.

class TalentDatabase:
    def __init__(self, excel_file='Atalent_submissions.xlsx'):
        self.file_path = os.path.join(excel_file)
    
    def load_data(self) -> pd.DataFrame:
        try:
            if not os.path.exists(self.file_path):
                raise FileNotFoundError(f"Database file not found at {self.file_path}")
            
            wb = load_workbook(self.file_path)
            ws = wb.active
            
            df = pd.read_excel(
                self.file_path,
                sheet_name=ws.title,
                header=0,
                engine='openpyxl'
            )
            
            expected_columns = [
                "Name", "Role", "Injective Role", "Experience", "Education", 
                "Location", "Availability", "Monthly Rate", "Skills", "Languages",
                "Discord", "Email", "Phone", "Telegram", "X", "Github",
                "Wallet Address", "Wallet Type", "NFT Holdings", "Token Holdings",
                "Portfolio", "CV", "Image url", "Bio", "Submission date", "Status"
            ]
            
            for col in expected_columns:
                if col not in df.columns:
                    df[col] = None
            
            if 'Submission date' in df.columns:
                df['Submission date'] = pd.to_datetime(df['Submission date'])
            
            return df
            
        except Exception as e:
            print(f"Error loading database: {e}")
            return pd.DataFrame()
    
    def get_by_wallet(self, wallet_address: str) -> pd.DataFrame:
        df = self.load_data()
        if not df.empty and 'Wallet Address' in df.columns:
            return df[df['Wallet Address'].str.lower() == wallet_address.lower()].copy()
        return pd.DataFrame()
    
    def get_talent_by_wallet(self, wallet_address: str) -> dict:
        try:
            wallet_data = self.get_by_wallet(wallet_address)
            
            if wallet_data.empty:
                return {
                    "info": "no",
                }
            
            submissions = wallet_data.to_dict('records')
            
            if len(submissions) == 1:
                return {
                    "info": "yes",
                    **submissions[0]
                }
            
            return {
                "info": "yes",
                "count": len(submissions),
                "wallet_address": wallet_address,
                "submissions": submissions
            }
            
        except Exception as e:
            return {
                "info": "no",
            }