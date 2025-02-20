import os
import pandas as pd

class XLSXReader:
    def __init__(self, file_path=None):
        if file_path is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))  
            self.file_path = os.path.join(base_dir, "eligable.xlsx") 
        else:
            self.file_path = file_path

    def read_csv(self):
        if not os.path.exists(self.file_path):
            raise FileNotFoundError(f"The file {self.file_path} does not exist.")

        df = pd.read_excel(self.file_path)
        
        required_columns = {'Address'}
        if not required_columns.issubset(df.columns):
            raise ValueError(f"The Excel file must contain the following columns: {required_columns}")

        df_filtered = df[['Address']]
        return df_filtered

    def check(self, wallet):
        df = self.read_csv()

        if wallet in df['Address'].values:
            return {"message": "Congratulations, You are eligible!"}
        else:
            return {"message": "Sadly, you are not eligible!"}