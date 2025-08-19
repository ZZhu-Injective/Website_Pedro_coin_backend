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
    
    def _process_transactions(self, transactions: List[Dict]) -> pd.DataFrame:
        """Process transactions into a DataFrame"""
        df = pd.DataFrame(transactions)
        
        # Convert timestamp
        if 'block_timestamp' in df.columns:
            df['block_timestamp'] = pd.to_datetime(
                df['block_timestamp'].str.replace(' UTC', ''),
                format='%Y-%m-%d %H:%M:%S.%f %z',
                errors='coerce'
            )
            
            if df['block_timestamp'].isna().any():
                df['block_timestamp'] = pd.to_datetime(
                    df['block_timestamp'],
                    errors='coerce'
                )
        
        # Convert numeric columns - fixed to handle errors properly
        numeric_cols = ['block_number', 'gas_used', 'gas_wanted', 'fee']
        for col in numeric_cols:
            if col in df.columns:
                try:
                    df[col] = pd.to_numeric(df[col])
                except (ValueError, TypeError):
                    # If conversion fails, keep original values but log the issue
                    print(f"Warning: Could not convert column '{col}' to numeric")
        
        return df
    
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
                try:
                    batch_df[col] = pd.to_numeric(batch_df[col])
                except (ValueError, TypeError):
                    batch_df[col] = batch_df[col]  # Keep original if conversion fails
        
        return batch_df
    
    def show_summary(self):
        """Displays a summary of fetched transactions"""
        print("\n=== TRANSACTION SUMMARY ===")
        print(f"Total transactions: {len(self.df)}")
        
        if 'block_number' in self.df.columns and not self.df.empty:
            print(f"Block range: {self.df['block_number'].min()} to {self.df['block_number'].max()}")
        
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

    def extract_messages(self) -> pd.DataFrame:
        """Extract and expand messages from transactions"""
        if self.df.empty or "messages" not in self.df.columns:
            return pd.DataFrame()
            
        # Create a list of all messages with transaction context
        all_messages = []
        for _, tx in self.df.iterrows():
            if not isinstance(tx['messages'], list):
                continue
                
            for msg in tx['messages']:
                if isinstance(msg, dict):
                    # Add transaction context to each message
                    msg_with_context = msg.copy()
                    msg_with_context['tx_hash'] = tx.get('hash', '')
                    msg_with_context['block_number'] = tx.get('block_number', '')
                    msg_with_context['block_timestamp'] = tx.get('block_timestamp', '')
                    all_messages.append(msg_with_context)
        
        return pd.DataFrame(all_messages)

    def analyze_transactions(self):
        """Perform comprehensive analysis of transactions"""
        if self.df.empty:
            print("No transactions to analyze")
            return
        
        def extract_message_info(message_str):
            try:
                if isinstance(message_str, str) and message_str.startswith('['):
                    messages = eval(message_str)
                    if messages and len(messages) > 0:
                        return messages[0].get('type', ''), messages[0].get('value', {})
                return '', {}
            except:
                return '', {}

        # Extract message type and details
        self.df[['msg_type', 'msg_value']] = self.df['messages'].apply(
            lambda x: pd.Series(extract_message_info(x))
        )

        # Function to extract recipient addresses
        def extract_recipients(logs_data):
            recipients = set()
            try:
                # Handle both string representation and actual list
                if isinstance(logs_data, str):
                    try:
                        # Try to parse the string as JSON/list
                        logs = eval(logs_data)
                    except:
                        return list(recipients)
                else:
                    logs = logs_data
                
                # Process the logs
                for log in logs:
                    if not isinstance(log, dict):
                        continue
                        
                    # Check if events exist in the log
                    events = log.get('events', [])
                    for event in events:
                        if not isinstance(event, dict):
                            continue
                            
                        attributes = event.get('attributes', [])
                        for attr in attributes:
                            if not isinstance(attr, dict):
                                continue
                                
                            key = attr.get('key', '')
                            value = attr.get('value', '')
                            
                            if not key or not value:
                                continue
                            
                            # Look for addresses in various attributes
                            if key in ['recipient', 'receiver', 'to', 'from', 'sender', 'spender']:
                                recipients.add(value)
                            
                            # Also check for contract addresses
                            if key == '_contract_address':
                                recipients.add(value)
        
                # Remove the current address from recipients
                if self.address in recipients:
                    recipients.remove(self.address)
                    
            except Exception as e:
                print(f"Error extracting recipients: {e}")
            
            return list(recipients)

        # Extract recipients from logs
        self.df['recipients'] = self.df['logs'].apply(extract_recipients)

        # Known legitimate contracts (you can expand this list)
        known_contracts = {
            'inj15ckgh6kdqg0x5p7curamjvqrsdw4cdzz5ky9v6',  # Common swap contract
            'inj1v77y5ttah96dc9qkcpc88ad7rce8n88e99t3m5',  # Talis protocol
            'inj1uq453kp4yda7ruc0axpmd9vzfm0fj62padhe0p'   # Another common contract
        }

        # Function to identify suspicious transactions
        def is_suspicious(tx):
            suspicious_flags = []
            
            # High gas fees
            if 'gas_fee' in tx and isinstance(tx['gas_fee'], dict):
                if 'amount' in tx['gas_fee'] and isinstance(tx['gas_fee']['amount'], list):
                    for amt in tx['gas_fee']['amount']:
                        if amt['denom'] == 'inj' and float(amt['amount']) > 1000000000000000:  # > 0.001 INJ
                            suspicious_flags.append('High gas fee')
            
            # Multi-send transactions (often airdrops or scam distributions)
            if '/cosmos.bank.v1beta1.MsgMultiSend' in str(tx.get('messages', '')):
                suspicious_flags.append('Multi-send transaction')
            
            # Unknown contracts
            if 'msg_value' in tx and isinstance(tx['msg_value'], dict):
                contract = tx['msg_value'].get('contract', '')
                if contract and contract not in known_contracts:
                    suspicious_flags.append('Unknown contract')
            
            # Small amounts to many addresses (potential dusting attack)
            if len(tx.get('recipients', [])) > 10:
                suspicious_flags.append('Many recipients')
            
            return suspicious_flags

        # Identify suspicious transactions
        self.df['suspicious_flags'] = self.df.apply(is_suspicious, axis=1)
        self.df['is_suspicious'] = self.df['suspicious_flags'].apply(lambda x: len(x) > 0)

        # Get all recipient addresses
        all_recipients = []
        for recipients in self.df['recipients']:
            all_recipients.extend(recipients)

        # Count transactions per address
        recipient_counts = pd.Series(all_recipients).value_counts()

        # Extract dApp information from message types
        def extract_dapp(msg_type):
            if 'wasm' in msg_type:
                return 'CosmWasm'
            elif 'staking' in msg_type:
                return 'Staking'
            elif 'bank' in msg_type:
                return 'Bank'
            elif 'distribution' in msg_type:
                return 'Distribution'
            elif 'injective.wasmx' in msg_type:
                return 'Injective WasmX'
            else:
                return 'Other'

        self.df['dapp'] = self.df['msg_type'].apply(extract_dapp)

        # Monthly transaction count
        self.df['month'] = pd.to_datetime(self.df['block_timestamp']).dt.to_period('M')
        monthly_counts = self.df.groupby('month').size()

        # Print results
        print("="*80)
        print("SUSPICIOUS TRANSACTIONS ANALYSIS")
        print("="*80)

        suspicious_txs = self.df[self.df['is_suspicious']]
        if len(suspicious_txs) > 0:
            print(f"\nFound {len(suspicious_txs)} potentially suspicious transactions:")
            for _, tx in suspicious_txs.iterrows():
                print(f"\nBlock {tx['block_number']} - {tx['block_timestamp']}")
                print(f"Type: {tx['msg_type']}")
                print(f"Flags: {', '.join(tx['suspicious_flags'])}")
                print(f"Hash: {tx['hash']}")
        else:
            print("\nNo suspicious transactions found.")

        print("\n" + "="*80)
        print("TOP 20 MOST TRANSACTED WALLETS")
        print("="*80)
        print(recipient_counts.head(20))

        print("\n" + "="*80)
        print("TOP 10 MOST USED dAPPS")
        print("="*80)
        dapp_counts = self.df['dapp'].value_counts()
        print(dapp_counts.head(10))

        print("\n" + "="*80)
        print("MONTHLY TRANSACTION COUNT")
        print("="*80)
        print(monthly_counts)

if __name__ == "__main__":
    address = "inj14rmguhlul3p30ntsnjph48nd5y2pqx2qwwf4u9"
    fetcher = ScamScannerChecker(address)
    df = fetcher.fetch_sequential_ranges()
    
    fetcher.analyze_transactions()