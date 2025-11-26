from odoo import http
from odoo.http import request
import base64
import csv
import io
import json


class KojtoHrTimeTrackingExportController(http.Controller):

    def _extract_date_range_from_domain(self, domain):
        """Recursively extract datetime_start date range from domain conditions."""
        date_from = None
        date_to = None

        for condition in domain:
            if isinstance(condition, list):
                # Check if it's a nested domain (starts with '&', '|', '!')
                if condition and condition[0] in ['&', '|', '!']:
                    # Recursively process nested conditions
                    nested_from, nested_to = self._extract_date_range_from_domain(condition[1:])
                    if nested_from:
                        date_from = nested_from
                    if nested_to:
                        date_to = nested_to
                # Check if it's a regular condition tuple
                elif len(condition) == 3:
                    field, operator, value = condition
                    if field == 'datetime_start':
                        if operator == '>=':
                            date_from = value
                        elif operator == '<=':
                            date_to = value
                        elif operator == '<':
                            date_to = value

        return date_from, date_to

    @http.route(['/kojto_hr/time_tracking/export_csv'], type='http', auth='user')
    def export_grouped_csv(self, payload=None, **kwargs):
        if not payload:
            return request.not_found()

        try:
            decoded = json.loads(base64.b64decode(payload).decode('utf-8'))
        except Exception:
            return request.not_found()

        model_name = decoded.get('model') or 'kojto.hr.time.tracking'
        domain = decoded.get('domain') or []
        if not domain:
            # Fallback to server-computed active_domain from the current action/view
            ctx_domain = (request.env.context or {}).get('active_domain')
            if ctx_domain:
                domain = ctx_domain
        group_by = decoded.get('group_by') or []

        env = request.env
        Model = env[model_name].with_context(
            lang=decoded.get('lang') or env.user.lang,
            tz=decoded.get('tz') or env.user.tz,
        )

        # If grouping not provided by the client, try recovering from server context
        if not group_by:
            ctx = request.env.context or {}
            recovered = ctx.get('ordered_groupby') or ctx.get('group_by') or ctx.get('groupby') or []
            if isinstance(recovered, str):
                recovered = [g.strip() for g in recovered.split(',') if g.strip()]
            group_by = list(recovered or [])

        # Still missing? fall back to a sensible default to avoid blocking the user
        if not group_by:
            group_by = ['employee_id', 'code_id']

        # Ensure Employee appears before Code if both are present (swap positions only)
        if 'employee_id' in group_by and 'code_id' in group_by:
            i = group_by.index('employee_id')
            j = group_by.index('code_id')
            if i > j:
                group_by[i], group_by[j] = group_by[j], group_by[i]

        # Build fields list: sum of total_hours plus group_by fields
        fields = ['total_hours:sum'] + group_by

        results = Model.read_group(domain, fields, groupby=group_by, lazy=False)

        # Compute total hours across all groups
        total_hours_all = 0.0
        for row in results:
            total_hours_all += row.get('total_hours_sum', row.get('total_hours', row.get('total_hours__sum', 0.0))) or 0.0

        # Extract date range from domain for the period header
        date_from, date_to = self._extract_date_range_from_domain(domain)

        # Format period string
        period_str = 'Period'
        if date_from or date_to:
            if date_from and date_to:
                # Extract just the date part (YYYY-MM-DD)
                period_str = f"Period: {str(date_from)[:10]} - {str(date_to)[:10]}"
            elif date_from:
                period_str = f"Period: From {str(date_from)[:10]}"
            elif date_to:
                period_str = f"Period: Until {str(date_to)[:10]}"

        # Prepare headers using field "string" labels. Support date groupings like "field:month"
        base_fields = [g.split(':', 1)[0] for g in group_by]
        fields_info = Model.fields_get(base_fields)
        headers = [fields_info.get(base, {}).get('string', base) for base in base_fields]
        headers.append('Hours')

        # Create CSV
        buffer = io.StringIO()
        writer = csv.writer(buffer, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)

        # Write period as first row with total hours in column C
        writer.writerow([period_str, '', round(total_hours_all, 2)])

        writer.writerow(headers)

        for row in results:
            flat_values = []
            for g in group_by:
                value = row.get(g)
                # Many2one returns (id, name)
                if isinstance(value, (list, tuple)) and len(value) == 2:
                    flat_values.append(value[1])
                else:
                    flat_values.append(value if value is not None else '')
            # Try different possible key names for the sum
            hours = row.get('total_hours_sum', row.get('total_hours', row.get('total_hours__sum', 0.0)))
            flat_values.append(hours)
            writer.writerow(flat_values)

        data = buffer.getvalue()
        buffer.close()

        # Prepend BOM for Excel compatibility
        content = ('\ufeff' + data).encode('utf-8')
        filename = 'time_tracking_grouped.csv'
        headers_resp = [
            ('Content-Type', 'text/csv; charset=utf-8'),
            ('Content-Disposition', f'attachment; filename="{filename}"'),
        ]
        return request.make_response(content, headers=headers_resp)


