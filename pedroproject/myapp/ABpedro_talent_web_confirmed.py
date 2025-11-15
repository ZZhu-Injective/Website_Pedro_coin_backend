import os
import pandas as pd
from datetime import datetime

#Get info from database about the talented people.

class TalentDataReaders:
    def __init__(self, file_path=None):
        if file_path is None:
            self.file_path = os.path.join('1.Atalent_submissions.xlsx')
        else:
            self.file_path = file_path

    def read_approved_talents(self):
        if not os.path.exists(self.file_path):
            raise FileNotFoundError(f"The file {self.file_path} does not exist.")

        df = pd.read_excel(self.file_path)

        required_columns = [
            "Name", "Role", "Injective Role", "Experience", "Education", "Location",
            "Availability", "Monthly Rate", "Skills", "Languages", "Discord", "Email",
            "Phone", "Telegram", "X", "Github", "Wallet Address", "Wallet Type",
            "NFT Holdings", "Token Holdings", "Portfolio", "CV", "Image url", "Bio",
            "Submission date", "Status"
        ]

        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise ValueError(f"Missing required columns: {missing_columns}")

        approved_df = df[df['Status'].str.lower() == 'approved']

        records = approved_df.to_dict(orient='records')

        for idx, record in enumerate(records, start=1):
            record['index'] = idx
            if isinstance(record.get('Submission date'), datetime):
                record['Submission date'] = record['Submission date'].strftime('%Y-%m-%d %H:%M:%S')

        return records
