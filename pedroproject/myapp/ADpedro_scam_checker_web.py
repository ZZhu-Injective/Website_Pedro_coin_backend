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
        
        if scam_wallet_file is None:
            scam_wallet_file = r"C:\Users\zonwi\Documents\GitHub\Website_Pedro_coin_backend\pedroproject\myapp\ADpedro_scam_wallet.json"
        
        self.scam_addresses = self._load_scam_addresses(scam_wallet_file)
    
    def _load_scam_addresses(self, scam_wallet_file: str) -> List[str]:
        """Load scam addresses from JSON file"""
        try:
            if not os.path.exists(scam_wallet_file):
                return []
                
            with open(scam_wallet_file, 'r') as f:
                data = json.load(f)
                scam_addresses = data.get("scam_addresses", [])
                return scam_addresses
        except (FileNotFoundError, json.JSONDecodeError, PermissionError) as e:
            return []
    
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
                batch_df['block_timestamp'].astype(str).str.replace(' UTC', ''),
                format='%Y-%m-%d %H:%M:%S.%f %z',
                errors='coerce'
            )
        
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
            return timestamp.strftime('%Y-%m-%d %H:%M:%S')
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
                    messages_list = eval(messages)
                    if isinstance(messages_list, list):
                        for msg in messages_list:
                            if isinstance(msg, dict) and 'type' in msg:
                                all_message_types.append(msg['type'])
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
                    logs = eval(logs_data)
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
                    logs = eval(logs_data)
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
            pass
        
        return list(recipients)

    def analyze_transactions(self) -> Dict[str, Any]:
        """Perform comprehensive analysis of transactions and return results as JSON"""
        if self.df.empty:
            return {"error": "No transactions to analyze"}
        
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
        
        if not self.df.empty and 'block_timestamp' in self.df.columns:
            valid_timestamps = self.df['block_timestamp'].dropna()
            if not valid_timestamps.empty:
                self.analysis_results["first_transaction_date"] = self._safe_format_timestamp(valid_timestamps.min())
                self.analysis_results["last_transaction_date"] = self._safe_format_timestamp(valid_timestamps.max())
        
        if 'block_number' in self.df.columns and not self.df.empty:
            self.analysis_results["block_range"] = {
                "min": int(self.df['block_number'].min()),
                "max": int(self.df['block_number'].max())
            }
        
        if 'tx_type' in self.df.columns:
            self.analysis_results["transaction_types"] = self.df['tx_type'].value_counts().to_dict()

        def extract_message_info(message_str):
            try:
                if pd.isna(message_str) or not message_str:
                    return '', {}
                    
                if isinstance(message_str, str) and message_str.startswith('['):
                    messages = eval(message_str)
                    if messages and len(messages) > 0:
                        return messages[0].get('type', ''), messages[0].get('value', {})
                return '', {}
            except:
                return '', {}

        self.df[['msg_type', 'msg_value']] = self.df['messages'].apply(
            lambda x: pd.Series(extract_message_info(x))
        )

        self.df['recipients'] = self.df['logs'].apply(self.extract_recipients)
        
        self.df['dapp_info'] = self.df['logs'].apply(self.extract_dapp_info)
        
        self.df['dapp_contracts'] = self.df['dapp_info'].apply(lambda x: x.get('contracts', []))
        self.df['dapp_actions'] = self.df['dapp_info'].apply(lambda x: x.get('actions', []))
        self.df['dapp_name'] = self.df['dapp_info'].apply(lambda x: x.get('dapp_name', 'Unknown'))

        known_contracts = {
            'inj15ckgh6kdqg0x5p7curamjvqrsdw4cdzz5ky9v6',  
            'inj1v77y5ttah96dc9qkcpc88ad7rce8n88e99t3m5', 
            'inj1uq453kp4yda7ruc0axpmd9vzfm0fj62padhe0p'
        }

        def is_suspicious(tx):
            suspicious_flags = []
            risk_score = 1
            
            scam_interactions = [addr for addr in tx['recipients'] if addr in self.scam_addresses]
            if scam_interactions:
                suspicious_flags.append(f"Interacted with known scam address(es): {', '.join(scam_interactions)}")
                risk_score = 10
            
            elif risk_score < 10:
                #unknown_contracts = [addr for addr in tx['dapp_contracts'] if addr not in known_contracts]
                #if unknown_contracts:
                #    suspicious_flags.append(f"Interacted with unknown contract(s): {', '.join(unknown_contracts)}")
                #    risk_score = min(risk_score + 5 * len(unknown_contracts), 8)
                
                # Check for high gas usage
                #if 'gas_used' in tx and not pd.isna(tx['gas_used']) and tx['gas_used'] > 500000:
                #    suspicious_flags.append(f"High gas usage: {tx['gas_used']}")
                #    risk_score = min(risk_score + 3, 8)
                None            
            return suspicious_flags, risk_score

        self.df[['suspicious_flags', 'risk_score']] = self.df.apply(
            lambda x: pd.Series(is_suspicious(x)), axis=1
        )
        self.df['is_suspicious'] = self.df['suspicious_flags'].apply(lambda x: len(x) > 0)
        
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

        if not self.df.empty:
            if scam_interaction_count > 0:
                scam_percentage = min(scam_interaction_count / len(self.df) * 2, 1.0)
                overall_risk_score = max(6, int(10 * scam_percentage))
            else:
                overall_risk_score = int(self.df['risk_score'].mean())
            
            overall_risk_score = min(overall_risk_score, 10)
            self.analysis_results["risk_score"] = overall_risk_score
        
        all_recipients = []
        for recipients in self.df['recipients']:
            all_recipients.extend(recipients)

        recipient_counts = pd.Series(all_recipients).value_counts()
        self.analysis_results["top_recipients"] = [
            {"address": addr, "count": int(count)} 
            for addr, count in recipient_counts.head(20).items()
        ]

        def extract_dapp(msg_type):
            if not msg_type:
                return 'Unknown'
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

        if 'block_timestamp' in self.df.columns and not self.df['block_timestamp'].dropna().empty:
            try:
                self.df['month'] = self.df['block_timestamp'].dt.tz_convert(None).dt.to_period('M')
                monthly_counts = self.df.groupby('month').size()
                self.analysis_results["monthly_activity"] = {
                    str(month): int(count) for month, count in monthly_counts.items()
                }
            except:
                self.analysis_results["monthly_activity"] = {"error": "Could not calculate monthly activity"}

        dapp_counts = self.df['dapp_name'].value_counts()
        self.analysis_results["dapp_usage"] = {
            dapp: int(count) for dapp, count in dapp_counts.head(10).items()
        }
        
        all_contracts = []
        for contracts in self.df['dapp_contracts']:
            all_contracts.extend(contracts)
        
        contract_counts = pd.Series(all_contracts).value_counts()
        self.analysis_results["contracts_interacted"] = {
            contract: int(count) for contract, count in contract_counts.head(10).items()
        }
        
        all_actions = []
        for actions in self.df['dapp_actions']:
            all_actions.extend(actions)
        
        action_counts = pd.Series(all_actions).value_counts()
        self.analysis_results["actions_performed"] = {
            action: int(count) for action, count in action_counts.head(10).items()
        }

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

        message_type_counts = self.extract_message_types()
        if not message_type_counts.empty:
            self.analysis_results["message_types"] = {
                msg_type: int(count) for msg_type, count in message_type_counts.items()
            }

        return self.analysis_results

if __name__ == "__main__":
    address = "inj1x6u08aa3plhk3utjk7wpyjkurtwnwp6dhudh0j"
    fetcher = ScamScannerChecker(address)
    df = fetcher.fetch_sequential_ranges()
    
    results = fetcher.analyze_transactions()
    print(results)
    
    #print(json.dumps(results, indent=2))