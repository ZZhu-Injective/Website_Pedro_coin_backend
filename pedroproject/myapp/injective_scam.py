from .models import ScamReport


class ScamDataReader:
    async def read_excel(self):
        # ordering = ['-id'] on the model gives newest-first, matching the
        # previous Excel "[::-1]" reverse behavior.
        records = []
        idx = 0
        async for r in ScamReport.objects.all():
            idx += 1
            records.append({
                'Address': r.address,
                'Time': r.time,
                'Project': r.project,
                'Amount': r.amount,
                'Info': r.info,
                'Group': r.group,
                'index': idx,
            })
        return records
