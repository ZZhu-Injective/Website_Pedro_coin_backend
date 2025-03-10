import os
import pandas as pd

class ScamDataReader:
    def __init__(self, file_path=None):
        if file_path is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))  
            self.file_path = os.path.join(base_dir, "scam.xlsx") 
        else:
            self.file_path = file_path

    def read_excel(self):
        if not os.path.exists(self.file_path):
            raise FileNotFoundError(f"The file {self.file_path} does not exist.")

        df = pd.read_excel(self.file_path)

        required_columns = [
            'Address', 'Time', 'Project', 'Amount', 'Info', 'Group'
        ]

        if len(df.columns) != len(required_columns):
            raise ValueError(f"The Excel file must have exactly {len(required_columns)} columns. Found {len(df.columns)} columns instead.")

        df = df[required_columns]

        df = df[::-1].reset_index(drop=True)

        records = df.to_dict(orient='records')
        for idx, record in enumerate(records, start=1):
            record['index'] = idx

        return records