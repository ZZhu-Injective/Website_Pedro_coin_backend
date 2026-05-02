from .models import Talent


class TalentDataReaders:
    async def read_approved_talents(self):
        records = []
        idx = 0
        qs = Talent.objects.filter(status__iexact='approved')
        async for t in qs:
            idx += 1
            record = t.to_excel_dict()
            record['index'] = idx
            records.append(record)
        return records
