import csv
from django.http import HttpResponse
from datetime import datetime


def export_csv(data, filename, headers=None):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv"'
    if not data:
        response.write('No data\n')
        return response
    if headers is None:
        headers = list(data[0].keys()) if isinstance(data[0], dict) else None
    writer = csv.writer(response)
    if headers:
        writer.writerow(headers)
    for row in data:
        if isinstance(row, dict):
            writer.writerow([str(v) for v in row.values()])
        else:
            writer.writerow([str(v) for v in row])
    return response
