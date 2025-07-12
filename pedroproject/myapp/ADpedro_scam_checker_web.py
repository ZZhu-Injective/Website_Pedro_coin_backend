import requests
import time
import pandas as pd
from typing import List, Dict

class ScamScannerChecker:
    def __init__(self, address: str):
        self.address = address
        self.base_url = f"https://sentry.exchange.grpc-web.injective.network/api/explorer/v1/accountTxs/{address}"
        self.df = pd.DataFrame()
        self.range_size = 100 
        self.current_block = 0
    
    def fetch_sequential_ranges(self) -> pd.DataFrame:
        while True:
            from_block = self.current_block
            to_block = from_block + self.range_size - 1

            try:
                batch = self._fetch_batch(from_block, to_block)
                if not batch:
                    break
                
                batch_df = self._process_batch(batch)
                self.df = pd.concat([self.df, batch_df], ignore_index=True)
                                
                self.current_block = to_block + 1
                time.sleep(0.3)  
                
            except Exception as e:
                print(f"Error fetching data: {e}")
                break
        
        if not self.df.empty:
            self.show_summary()
        
        return self.df
    
    def _fetch_batch(self, from_block: int, to_block: int) -> List[Dict]:
        params = {
            "from_number": from_block,
            "to_number": to_block
        }
        
        response = requests.get(
            self.base_url,
            params=params,
            timeout=15,
            headers={'User-Agent': 'InjectiveTxFetcher/1.0'}
        )
        response.raise_for_status()
        return response.json().get("data", [])
    
    def _process_batch(self, batch: List[Dict]) -> pd.DataFrame:
        batch_df = pd.DataFrame(batch)
        
        if 'block_timestamp' in batch_df.columns:
            batch_df['block_timestamp'] = pd.to_datetime(
                batch_df['block_timestamp'].str.replace(' UTC', ''),
                format='%Y-%m-%d %H:%M:%S.%f %z',
                errors='coerce'
            )
            
            if batch_df['block_timestamp'].isna().any():
                batch_df['block_timestamp'] = pd.to_datetime(
                    batch_df['block_timestamp'],
                    errors='coerce'
                )
        
        numeric_cols = ['block_number', 'gas_used', 'gas_wanted', 'fee']
        for col in numeric_cols:
            if col in batch_df.columns:
                batch_df[col] = pd.to_numeric(batch_df[col], errors='ignore')
        
        return batch_df
    
    def show_summary(self):
        """Displays a summary of fetched transactions"""
        print("\n=== TRANSACTION SUMMARY ===")
        print(f"Total transactions: {len(self.df)}")
        print(f"Blocks covered: {self.current_block - self.range_size} to {self.current_block - 1}")
        
        if 'tx_type' in self.df.columns:
            print("\nTransaction Types:")
            print(self.df['tx_type'].value_counts().to_string())
        
        if not self.df.empty:
            print("\nFirst transaction:")
            print(self.df.iloc[0][['block_number', 'block_timestamp', 'tx_type']].to_string())
            print("\nLast transaction:")
            print(self.df.iloc[-1][['block_number', 'block_timestamp', 'tx_type']].to_string())
    
    def get_transactions(self) -> pd.DataFrame:
        """Returns the cleaned DataFrame"""
        return self.df

if __name__ == "__main__":
    address = "inj14rmguhlul3p30ntsnjph48nd5y2pqx2qwwf4u9"
    fetcher = ScamScannerChecker(address)
    df = fetcher.fetch_sequential_ranges()
    
    # Save the messages column to Excel
    if not df.empty and "messages" in df.columns:
        # Create a DataFrame with just the messages column
        messages_df = pd.DataFrame(df["messages"])
        messages_df.to_excel("messages.xlsx", index=False)
        print("Saved messages to messages.xlsx")
    
    # Save the entire DataFrame to Excel
    df.to_excel("all_transactions.xlsx", index=False)
    print("Saved all transactions to all_transactions.xlsx")