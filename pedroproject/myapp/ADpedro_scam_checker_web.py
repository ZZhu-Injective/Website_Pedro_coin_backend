import requests
import time
import pandas as pd
import json
import os
from typing import List, Dict, Any, Union
from datetime import datetime

class ScamScannerChecker:
    def __init__(self, address: str, scam_wallet_file: str = None):
        self.address = address
        self.base_url = f"https://sentry.exchange.grpc-web.injective.network/api/explorer/v1/accountTxs/{address}"
        self.df = pd.DataFrame()
        self.range_size = 100 
        self.current_block = 0
        self.analysis_results = {}
        
        script_dir = os.path.dirname(os.path.abspath(__file__))
        
        if scam_wallet_file is None:
            env_path = os.environ.get('SCAM_DB_PATH')
            if env_path and os.path.exists(env_path):
                scam_wallet_file = env_path
            else:
                possible_paths = [
                    os.path.join(script_dir, "ADpedro_scam_wallet.json"),
                ]
                
                for path in possible_paths:
                    if os.path.exists(path):
                        scam_wallet_file = path
                        break
                else:
                    scam_wallet_file = None
        
        self.scam_addresses = self._load_scam_addresses(scam_wallet_file)
    
    def _load_scam_addresses(self, scam_wallet_file: str) -> List[str]:
        """Load scam addresses from JSON file with better error handling"""
        try:
            if not os.path.exists(scam_wallet_file):
                print(f"Scam addresses file not found: {scam_wallet_file}")
                return []
                
            with open(scam_wallet_file, 'r') as f:
                data = json.load(f)
                scam_addresses = data.get("scam_addresses", [])
                return scam_addresses
        except (FileNotFoundError, json.JSONDecodeError, PermissionError) as e:
            print(f"Error loading scam addresses: {e}")
            return []
        except Exception as e:
            print(f"Unexpected error loading scam addresses: {e}")
            return []
    
    def fetch_sequential_ranges(self) -> pd.DataFrame:
        """Fetch transactions in sequential blocks with improved error handling"""
        max_retries = 3
        retry_delay = 1  # seconds
        
        while True:
            from_block = self.current_block
            to_block = from_block + self.range_size - 1

            for attempt in range(max_retries):
                try:
                    batch = self._fetch_batch(from_block, to_block)
                    if not batch:
                        print(f"No more transactions found from block {from_block}")
                        return self.df
                    
                    batch_df = self._process_batch(batch)
                    self.df = pd.concat([self.df, batch_df], ignore_index=True)
                                    
                    self.current_block = to_block + 1
                    time.sleep(0.3)  
                    break  # Success, break out of retry loop
                    
                except requests.exceptions.RequestException as e:
                    print(f"Network error fetching blocks {from_block}-{to_block}: {e}")
                    if attempt < max_retries - 1:
                        print(f"Retrying in {retry_delay} seconds...")
                        time.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                    else:
                        print(f"Failed after {max_retries} attempts. Stopping.")
                        return self.df
                except Exception as e:
                    print(f"Error processing blocks {from_block}-{to_block}: {e}")
                    break
        
        if not self.df.empty:
            self.show_summary()
        
        return self.df
    
    def _fetch_batch(self, from_block: int, to_block: int) -> List[Dict]:
        """Fetch a batch of transactions with timeout and error handling"""
        params = {
            "from_number": from_block,
            "to_number": to_block
        }
        
        response = requests.get(
            self.base_url,
            params=params,
            timeout=30,  # Increased timeout
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        )
        response.raise_for_status()
        return response.json().get("data", [])
    
    def _process_batch(self, batch: List[Dict]) -> pd.DataFrame:
        """Process a batch of transactions into a DataFrame"""
        if not batch:
            return pd.DataFrame()
            
        batch_df = pd.DataFrame(batch)
        
        if 'block_timestamp' in batch_df.columns:
            # Handle different timestamp formats
            try:
                batch_df['block_timestamp'] = pd.to_datetime(
                    batch_df['block_timestamp'].astype(str).str.replace(' UTC', ''),
                    format='%Y-%m-%d %H:%M:%S.%f %z',
                    errors='coerce'
                )
            except:
                try:
                    batch_df['block_timestamp'] = pd.to_datetime(
                        batch_df['block_timestamp'], errors='coerce'
                    )
                except:
                    batch_df['block_timestamp'] = None
        
        numeric_cols = ['block_number', 'gas_used', 'gas_wanted', 'fee']
        for col in numeric_cols:
            if col in batch_df.columns:
                try:
                    batch_df[col] = pd.to_numeric(batch_df[col], errors='coerce')
                except (ValueError, TypeError):
                    batch_df[col] = batch_df[col]
        
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
            first_tx = self.df.iloc[0]
            timestamp_str = self._safe_format_timestamp(first_tx.get('block_timestamp'))
            print(f"Block: {first_tx.get('block_number')}, Timestamp: {timestamp_str}, Type: {first_tx.get('tx_type')}")
            
            print("\nLast transaction:")
            last_tx = self.df.iloc[-1]
            timestamp_str = self._safe_format_timestamp(last_tx.get('block_timestamp'))
            print(f"Block: {last_tx.get('block_number')}, Timestamp: {timestamp_str}, Type: {last_tx.get('tx_type')}")
    
    def _safe_format_timestamp(self, timestamp) -> str:
        """Safely format timestamp, handling NaT values"""
        if pd.isna(timestamp) or timestamp is None:
            return "Unknown"
        try:
            if hasattr(timestamp, 'strftime'):
                return timestamp.strftime('%Y-%m-%d %H:%M:%S')
            else:
                return str(timestamp)
        except (ValueError, AttributeError):
            return "Invalid timestamp"
    
    def get_transactions(self) -> pd.DataFrame:
        """Returns the cleaned DataFrame"""
        return self.df

    def extract_message_types(self):
        """Extract and count message types from transactions"""
        if self.df.empty or "messages" not in self.df.columns:
            return pd.Series()
        
        all_message_types = []
        
        for _, tx in self.df.iterrows():
            messages = tx['messages']
            
            if isinstance(messages, str):
                try:
                    # Use json.loads instead of eval for security
                    if messages.startswith('[') and messages.endswith(']'):
                        messages_list = json.loads(messages)
                        if isinstance(messages_list, list):
                            for msg in messages_list:
                                if isinstance(msg, dict) and 'type' in msg:
                                    all_message_types.append(msg['type'])
                except json.JSONDecodeError:
                    # Fallback to simple string parsing if JSON fails
                    if 'type' in messages:
                        all_message_types.append(messages.split('"type":')[1].split('"')[1])
                except:
                    continue
            elif isinstance(messages, list):
                for msg in messages:
                    if isinstance(msg, dict) and 'type' in msg:
                        all_message_types.append(msg['type'])
        
        if all_message_types:
            message_type_counts = pd.Series(all_message_types).value_counts()
            return message_type_counts.head(10)
        else:
            return pd.Series()

    def extract_dapp_info(self, logs_data):
        """Extract dApp information from transaction logs"""
        dapp_info = {
            'contracts': set(),
            'actions': set(),
            'dapp_name': 'Unknown'
        }
        
        try:
            # Handle NaN/float values
            if pd.isna(logs_data) or not logs_data:
                return dapp_info
                
            if isinstance(logs_data, str):
                try:
                    logs = json.loads(logs_data) if logs_data.startswith('[') else eval(logs_data)
                except:
                    return dapp_info
            else:
                logs = logs_data
            
            if not isinstance(logs, list):
                return dapp_info
                
            dapp_contracts = {
                'inj15ckgh6kdqg0x5p7curamjvqrsdw4cdzz5ky9v6': 'Helix Protocol',
                'inj1c6lxety9hqn9q4khwqvjcfa24c2qeqvvfsg4fm': 'Some Token Contract',
                'inj1cc6v7luq08p74h2nlrd6j5lcu0t8jqyg3gqt8j': 'Talis Protocol',
                'inj1v77y5ttah96dc9qkcpc88ad7rce8n88e99t3m5': 'Talis Protocol',
                'inj1uq453kp4yda7ruc0axpmd9vzfm0fj62padhe0p': 'Hydro Protocol',
                'inj18xg2xfhv36v4z7dr3ldqnm43fzukqgsafyyg63': 'Fee Recipient'
            }
            
            for log in logs:
                if not isinstance(log, dict):
                    continue
                    
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
                        
                        if key == '_contract_address' and value:
                            dapp_info['contracts'].add(value)
                            if value in dapp_contracts:
                                dapp_info['dapp_name'] = dapp_contracts[value]
                        
                        if key == 'action' and value:
                            dapp_info['actions'].add(value)
            
            dapp_info['contracts'] = list(dapp_info['contracts'])
            dapp_info['actions'] = list(dapp_info['actions'])
            
        except Exception as e:
            # Silently fail - this is expected for some transactions
            pass
        
        return dapp_info

    def extract_recipients(self, logs_data):
        """Extract recipients from transaction logs"""
        recipients = set()
        try:
            if pd.isna(logs_data) or not logs_data:
                return list(recipients)
                
            if isinstance(logs_data, str):
                try:
                    logs = json.loads(logs_data) if logs_data.startswith('[') else eval(logs_data)
                except:
                    return list(recipients)
            else:
                logs = logs_data
            
            if not isinstance(logs, list):
                return list(recipients)
                
            for log in logs:
                if not isinstance(log, dict):
                    continue
                    
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
                        
                        if key in ['recipient', 'receiver', 'to', 'from', 'sender', 'spender']:
                            recipients.add(value)
                        
                        if key == '_contract_address':
                            recipients.add(value)
    
            if self.address in recipients:
                recipients.remove(self.address)
                
        except Exception as e:
            # Silently fail - this is expected for some transactions
            pass
        
        return list(recipients)

    def analyze_transactions(self) -> Dict[str, Any]:
        """Perform comprehensive analysis of transactions and return results as JSON"""
        if self.df.empty:
            return {"error": "No transactions to analyze"}
        
        # Initialize results with basic info
        self.analysis_results = {
            "address": self.address,
            "total_transactions": len(self.df),
            "first_transaction_date": None,
            "last_transaction_date": None,
            "block_range": {},
            "transaction_types": {},
            "dapp_usage": {},
            "contracts_interacted": {},
            "actions_performed": {},
            "suspicious_transactions": [],
            "top_recipients": [],
            "monthly_activity": {},
            "message_types": {},
            "risk_score": 0,
            "scam_interactions": 0,
            "scam_addresses_loaded": len(self.scam_addresses),
            "scam_interaction_details": []
        }
        
        # Handle timestamps
        if not self.df.empty and 'block_timestamp' in self.df.columns:
            valid_timestamps = self.df['block_timestamp'].dropna()
            if not valid_timestamps.empty:
                self.analysis_results["first_transaction_date"] = self._safe_format_timestamp(valid_timestamps.min())
                self.analysis_results["last_transaction_date"] = self._safe_format_timestamp(valid_timestamps.max())
        
        # Block range
        if 'block_number' in self.df.columns and not self.df.empty:
            self.analysis_results["block_range"] = {
                "min": int(self.df['block_number'].min()),
                "max": int(self.df['block_number'].max())
            }
        
        # Transaction types
        if 'tx_type' in self.df.columns:
            self.analysis_results["transaction_types"] = self.df['tx_type'].value_counts().to_dict()

        # Extract message info
        def extract_message_info(message_str):
            try:
                if pd.isna(message_str) or not message_str:
                    return '', {}
                    
                if isinstance(message_str, str) and message_str.startswith('['):
                    try:
                        messages = json.loads(message_str)
                    except json.JSONDecodeError:
                        messages = eval(message_str)
                        
                    if messages and len(messages) > 0:
                        return messages[0].get('type', ''), messages[0].get('value', {})
                return '', {}
            except:
                return '', {}

        self.df[['msg_type', 'msg_value']] = self.df['messages'].apply(
            lambda x: pd.Series(extract_message_info(x))
        )

        # Extract recipients and dapp info
        self.df['recipients'] = self.df['logs'].apply(self.extract_recipients)
        self.df['dapp_info'] = self.df['logs'].apply(self.extract_dapp_info)
        self.df['dapp_contracts'] = self.df['dapp_info'].apply(lambda x: x.get('contracts', []))
        self.df['dapp_actions'] = self.df['dapp_info'].apply(lambda x: x.get('actions', []))
        self.df['dapp_name'] = self.df['dapp_info'].apply(lambda x: x.get('dapp_name', 'Unknown'))

        # Check for suspicious transactions
        def is_suspicious(tx):
            suspicious_flags = []
            risk_score = 1
                        
            # Extract message type from the transaction
            message_type = ''
            try:
                if 'msg_type' in tx and tx['msg_type']:
                    message_type = tx['msg_type']
                elif 'messages' in tx and tx['messages']:
                    # Try to extract message type from messages field
                    messages = tx['messages']
                    if isinstance(messages, str):
                        if messages.startswith('['):
                            try:
                                messages_list = json.loads(messages)
                                if messages_list and isinstance(messages_list, list) and len(messages_list) > 0:
                                    message_type = messages_list[0].get('type', '')
                            except:
                                # Fallback to string parsing
                                if '"type":' in messages:
                                    message_type = messages.split('"type":')[1].split('"')[1]
            except:
                pass
            
            # Check if this is a multi-send transaction
            is_multi_send = any(keyword in message_type.lower() for keyword in 
                            ['multisend', 'multi_send', 'multi-send', '/cosmos.bank.v1beta1.MsgMultiSend'])
            
            # Check for scam interactions, but exclude if it's a multi-send transaction
            scam_interactions = []
            if not is_multi_send:
                scam_interactions = [addr for addr in tx['recipients'] if addr in self.scam_addresses]
            
            if scam_interactions:
                suspicious_flags.append(f"Interacted with known scam address(es): {', '.join(scam_interactions)}")
                risk_score = 10
            
            return suspicious_flags, risk_score

        self.df[['suspicious_flags', 'risk_score']] = self.df.apply(
            lambda x: pd.Series(is_suspicious(x)), axis=1
        )
        self.df['is_suspicious'] = self.df['suspicious_flags'].apply(lambda x: len(x) > 0)
        
        # Count scam interactions
        scam_interaction_count = 0
        scam_interaction_details = []
        
        for _, tx in self.df.iterrows():
            scam_addresses_in_tx = [addr for addr in tx['recipients'] if addr in self.scam_addresses]
            if scam_addresses_in_tx:
                scam_interaction_count += len(scam_addresses_in_tx)
                scam_interaction_details.append({
                    "block_number": int(tx['block_number']),
                    "timestamp": self._safe_format_timestamp(tx.get('block_timestamp')),
                    "hash": tx.get('hash', 'Unknown'),
                    "scam_addresses": scam_addresses_in_tx,
                    "risk_score": int(tx['risk_score'])
                })
        
        self.analysis_results["scam_interactions"] = scam_interaction_count
        self.analysis_results["scam_interaction_details"] = scam_interaction_details

        # Calculate overall risk score
        if not self.df.empty:
            if scam_interaction_count > 0:
                scam_percentage = min(scam_interaction_count / len(self.df) * 2, 1.0)
                overall_risk_score = max(6, int(10 * scam_percentage))
            else:
                overall_risk_score = int(self.df['risk_score'].mean())
            
            overall_risk_score = min(overall_risk_score, 10)
            self.analysis_results["risk_score"] = overall_risk_score
        
        # Top recipients
        all_recipients = []
        for recipients in self.df['recipients']:
            all_recipients.extend(recipients)

        recipient_counts = pd.Series(all_recipients).value_counts()
        self.analysis_results["top_recipients"] = [
            {"address": addr, "count": int(count)} 
            for addr, count in recipient_counts.head(20).items()
        ]

        # Monthly activity
        if 'block_timestamp' in self.df.columns and not self.df['block_timestamp'].dropna().empty:
            try:
                self.df['month'] = self.df['block_timestamp'].dt.to_period('M')
                monthly_counts = self.df.groupby('month').size()
                self.analysis_results["monthly_activity"] = {
                    str(month): int(count) for month, count in monthly_counts.items()
                }
            except:
                self.analysis_results["monthly_activity"] = {"error": "Could not calculate monthly activity"}

        # Dapp usage
        dapp_counts = self.df['dapp_name'].value_counts()
        self.analysis_results["dapp_usage"] = {
            dapp: int(count) for dapp, count in dapp_counts.head(10).items()
        }
        
        # Contracts interacted with
        all_contracts = []
        for contracts in self.df['dapp_contracts']:
            all_contracts.extend(contracts)
        
        contract_counts = pd.Series(all_contracts).value_counts()
        self.analysis_results["contracts_interacted"] = {
            contract: int(count) for contract, count in contract_counts.head(10).items()
        }
        
        # Actions performed
        all_actions = []
        for actions in self.df['dapp_actions']:
            all_actions.extend(actions)
        
        action_counts = pd.Series(all_actions).value_counts()
        self.analysis_results["actions_performed"] = {
            action: int(count) for action, count in action_counts.head(10).items()
        }

        # Suspicious transactions
        suspicious_txs = self.df[self.df['is_suspicious']]
        for _, tx in suspicious_txs.iterrows():
            self.analysis_results["suspicious_transactions"].append({
                "block_number": int(tx['block_number']),
                "timestamp": self._safe_format_timestamp(tx.get('block_timestamp')),
                "type": tx.get('msg_type', 'Unknown'),
                "flags": tx['suspicious_flags'],
                "hash": tx.get('hash', 'Unknown'),
                "risk_score": int(tx['risk_score'])
            })

        # Message types
        message_type_counts = self.extract_message_types()
        if not message_type_counts.empty:
            self.analysis_results["message_types"] = {
                msg_type: int(count) for msg_type, count in message_type_counts.items()
            }

        return self.analysis_results

# Example usage
if __name__ == "__main__":
    address = "inj1x6u08aa3plhk3utjk7wpyjkurtwnwp6dhudh0j"
    fetcher = ScamScannerChecker(address)
    df = fetcher.fetch_sequential_ranges()
    
    results = fetcher.analyze_transactions()
    print(json.dumps(results, indent=2))