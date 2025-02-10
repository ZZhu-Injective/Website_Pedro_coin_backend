import os
import pandas as pd

class CSVReader:
    def __init__(self, file_path=None):
        if file_path is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))  # Directory of the current script
            self.file_path = os.path.join(base_dir, "checker.csv")  # File is in the same directory as the script
        else:
            self.file_path = file_path

    def read_csv(self):
        if not os.path.exists(self.file_path):
            raise FileNotFoundError(f"The file {self.file_path} does not exist.")

        df = pd.read_csv(self.file_path)
        required_columns = {'Role Name', 'Wallet Address'}
        if not required_columns.issubset(df.columns):
            raise ValueError(f"The CSV file must contain the following columns: {required_columns}")

        df_filtered = df[['Role Name', 'Wallet Address']]
        return df_filtered

    def check(self, wallet):
        df = self.read_csv()

        if wallet in df['Wallet Address'].values:
            role = df.loc[df['Wallet Address'] == wallet, 'Role Name'].values[0]

            if role == "Raccoon OG":
                return {"message": "Congratulations, You are eligible for OG and WL spot!"}
            elif role == "Raccoon WL":
                return {"message": "Congratulations, You are eligible for WL spots!"}
        else:
            return {"message": "Sadly, you are not eligible for WL or OG."}