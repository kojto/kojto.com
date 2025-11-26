from odoo import api, fields, models, tools
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta, time
import pytz
import logging

_logger = logging.getLogger(__name__)


class KojtoHrCalendarEvent(models.Model):
    _name = "kojto.hr.calendar.event"
    _description = "Kojto Hr Calendar Event"
    _auto = False  # Disable automatic table creation
    _order = "datetime_start desc"

    external_id = fields.Char(string="External ID", readonly=True)
    name = fields.Char(string="Name", readonly=True)
    event_type = fields.Selection(
        [
            ("time_tracking", "Time Tracking"),
            ("leave", "Leave"),
            ("business_trip", "Business Trip"),
        ],
        string="Event Type",
        default="time_tracking"
    )
    employee_id = fields.Many2one("kojto.hr.employees", string="Employee")
    user_id = fields.Many2one(related="employee_id.user_id", string="Associated User")
    datetime_start = fields.Datetime(string="From", required=True)
    datetime_end = fields.Datetime(string="To")

    time_tracking_start = fields.Float(
        string="From",
        compute='_compute_time_tracking_start',
        inverse='_inverse_time_tracking_start',
        default=lambda self: self._get_default_time_tracking_start())

    time_tracking_end = fields.Float(
        string="To",
        compute='_compute_time_tracking_end',
        inverse='_inverse_time_tracking_end',
        default=lambda self: self._get_default_time_tracking_end())

    source_model = fields.Char(string="Source Model", readonly=True)
    source_record_id = fields.Integer(string="Source Record ID", readonly=True)
    subcode_id = fields.Many2one("kojto.commission.subcodes", string="Subcode")
    subcode_description = fields.Char(related="subcode_id.description")
    total_hours = fields.Float(string="Hours", readonly=True)
    comment = fields.Char(string="Comment")
    leave_type_id = fields.Many2one("kojto.hr.leave.type", string="Leave Type")
    reason = fields.Char(string="Reason")
    leave_status = fields.Selection(
        selection=[
            ("approved", "Approved"),
            ("denied", "Denied"),
            ("pending", "Pending")
        ],
        string="Status",
        readonly=True,
        copy=False
    )
    code_id = fields.Many2one("kojto.commission.codes", string="Code", readonly=True)
    destination = fields.Char(string="Destination", readonly=True)
    business_purpose = fields.Char(string="Business Purpose", readonly=True)
    color = fields.Char(string="Color", readonly=True)
    all_day = fields.Boolean(string="All Day", default=False)
    create = fields.Boolean(string="Create", default=True)
    delete = fields.Boolean(string="Delete", default=True)

    face_recognition_times_display = fields.Char(
        string="Terminal",
        compute='_compute_fr_times',
        store=False,
        readonly=True
    )

    face_recognition_times_display = fields.Char(
        string="Terminal",
        compute='_compute_fr_times',
        store=False,
        readonly=True
    )

    start_date_only_display = fields.Date(
        string='Date Only',
        compute='_compute_start_date_only',
        inverse='_inverse_start_date_only',
        store=False
    )

    end_date_only_display = fields.Date(
        string='Date Only',
        compute='_compute_end_date_only',
        inverse='_inverse_end_date_only',
        store=False
    )

    @api.depends('datetime_start')
    def _compute_start_date_only(self):
        for record in self:
            if record.datetime_start:
                record.start_date_only_display = record.datetime_start.date()
            else:
                record.start_date_only_display = False

    def _inverse_start_date_only(self):
        for record in self:
            if record.event_type != 'leave':
                continue
            if record.start_date_only_display:
                record.datetime_start = datetime.combine(record.start_date_only_display, time.min)
            else:
                record.datetime_start = False

    @api.depends('datetime_end')
    def _compute_end_date_only(self):
        for record in self:
            if record.datetime_end:
                record.end_date_only_display = record.datetime_end.date()
            else:
                record.end_date_only_display = False

    def _inverse_end_date_only(self):
        for record in self:
            if record.event_type != 'leave':
                continue
            if record.end_date_only_display:
                record.datetime_end = datetime.combine(record.end_date_only_display, time.max)
            else:
                record.datetime_end = False


    def init(self):
        tools.drop_view_if_exists(self._cr, self._table)
        # Build optional Face Recognition join only if the model/table exists
        fr_join_sql = ""
        try:
            # Accessing the model will raise KeyError if the module/model is not installed
            _ = self.env['kojto.hr.face.recognition']
            fr_join_sql = """
                    LEFT JOIN (
                        SELECT
                            employee_id,
                            DATE_TRUNC('day', datetime_taken) AS dt,
                            STRING_AGG(TO_CHAR(datetime_taken, 'HH24:MI'), ', ' ORDER BY datetime_taken) AS fr_times
                        FROM kojto_hr_face_recognition
                        WHERE employee_id IS NOT NULL AND datetime_taken IS NOT NULL
                        GROUP BY employee_id, DATE_TRUNC('day', datetime_taken)
                    ) fr ON fr.employee_id = h.employee_id AND fr.dt = DATE_TRUNC('day', h.datetime_start)
            """
        except KeyError:
            fr_join_sql = ""
        self._cr.execute(
            """
            CREATE OR REPLACE VIEW {} AS (
                SELECT * FROM (
                    SELECT
                        7000000 + w.id AS id,
                        'wd_' || w.id AS external_id,
                        w.description AS name,
                        'working_day' AS event_type,
                        e.id AS employee_id,
                        e.user_id AS user_id,
                        w.date::timestamp AS datetime_start,
                        w.date::timestamp + INTERVAL '23 hours 59 minutes' AS datetime_end,
                        NULL::float AS time_tracking_start,
                        NULL::float AS time_tracking_end,
                        'kojto.hr.working.days' AS source_model,
                        w.id AS source_record_id,
                        NULL::integer AS subcode_id,
                        NULL::float AS total_hours,
                        NULL AS comment,
                        NULL::integer AS leave_type_id,
                        NULL AS reason,
                        NULL AS leave_status,
                        NULL::integer AS code_id,
                        NULL AS destination,
                        NULL AS business_purpose,
                        CASE
                            WHEN w.day_type = 'weekend' THEN '#ffcdd2'
                            WHEN w.day_type = 'public_holiday' THEN '#ff6bbc'
                            ELSE '#c8e6c9'
                        END AS color,
                        1 AS all_day,
                        0 AS create,
                        0 AS delete
                    FROM kojto_hr_working_days w
                    CROSS JOIN kojto_hr_employees e
                    WHERE w.is_working_day = false AND w.description != 'Weekend'
                UNION ALL
                    SELECT
                        1000000 + b.id AS id,
                        'bt_' || b.id AS external_id,
                        CONCAT(b.name, ' - ', b.business_purpose) AS name,
                        'business_trip' AS event_type,
                        b.employee_id,
                        e.user_id AS user_id,
                        b.date_start::timestamp AS datetime_start,
                        b.date_end::timestamp + INTERVAL '23 hours 59 minutes' AS datetime_end,
                        NULL::float AS time_tracking_start,
                        NULL::float AS time_tracking_end,
                        'kojto.hr.business.trips' AS source_model,
                        b.id AS source_record_id,
                        NULL::integer AS subcode_id,
                        NULL::float AS total_hours,
                        NULL AS comment,
                        NULL::integer AS leave_type_id,
                        NULL AS reason,
                        NULL AS leave_status,
                        b.code_id,
                        b.destination,
                        b.business_purpose,
                        '#e1bee7' as color,
                        1 AS all_day,
                        1 AS create,
                        0 AS delete
                    FROM kojto_hr_business_trips b
                    LEFT JOIN kojto_hr_employees e ON b.employee_id = e.id
                    WHERE b.date_start IS NOT NULL AND b.date_end IS NOT NULL
                UNION ALL
                    SELECT
                        2000000 + l.id AS id,
                        'lv_' || l.id AS external_id,
                        CONCAT(lt.name, ' - ', l.reason ) AS name,
                        'leave' AS event_type,
                        l.employee_id,
                        e.user_id AS user_id,
                        l.date_start::timestamp AS datetime_start,
                        l.date_end::timestamp + INTERVAL '23 hours 59 minutes' AS datetime_end,
                        NULL::float AS time_tracking_start,
                        NULL::float AS time_tracking_end,
                        'kojto.hr.leave.management' AS source_model,
                        l.id AS source_record_id,
                        NULL::integer AS subcode_id,
                        NULL::float AS total_hours,
                        NULL AS comment,
                        l.leave_type_id,
                        l.reason,
                        l.leave_status,
                        NULL::integer AS code_id,
                        NULL AS destination,
                        NULL AS business_purpose,
                        lt.color AS color,
                        1 AS all_day,
                        1 AS create,
                        1 AS delete
                    FROM kojto_hr_leave_management l
                    LEFT JOIN kojto_hr_employees e ON l.employee_id = e.id
                    LEFT JOIN kojto_hr_leave_type lt ON l.leave_type_id = lt.id
                    WHERE l.leave_status != 'denied' AND l.date_start IS NOT NULL AND l.date_end IS NOT NULL
                UNION ALL
                    SELECT
                        3000000 + t.id AS id,
                        'tt_' || t.id AS external_id,
                        CONCAT(s.name, ', ', ROUND(t.total_hours::numeric, 2), ', ', t.comment) AS name,
                        'time_tracking' AS event_type,
                        t.employee_id,
                        e.user_id AS user_id,
                        t.datetime_start,
                        t.datetime_end,
                        EXTRACT(EPOCH FROM t.datetime_start::time) / 3600.0 AS time_tracking_start,
                        EXTRACT(EPOCH FROM t.datetime_end::time) / 3600.0 AS time_tracking_end,
                        'kojto.hr.time.tracking' AS source_model,
                        t.id AS source_record_id,
                        t.subcode_id,
                        t.total_hours,
                        t.comment,
                        NULL::integer AS leave_type_id,
                        NULL AS reason,
                        NULL AS leave_status,
                        NULL::integer AS code_id,
                        NULL AS destination,
                        NULL AS business_purpose,
                        '1' AS color,
                        0 AS all_day,
                        1 AS create,
                        1 AS delete
                    FROM kojto_hr_time_tracking t
                    LEFT JOIN kojto_hr_employees e ON t.employee_id = e.id
                    LEFT JOIN kojto_commission_subcodes s ON t.subcode_id = s.id
                    WHERE t.datetime_start IS NOT NULL AND t.datetime_end IS NOT NULL
                UNION ALL
                    SELECT
                       6000000 + ROW_NUMBER() OVER (ORDER BY h.employee_id, DATE_TRUNC('day', h.datetime_start)) AS id,
                        'ttt_' || h.employee_id || '_' || DATE_TRUNC('day', h.datetime_start) AS external_id,
                        CONCAT(
                            'Total: ',
                            FLOOR(SUM(h.total_hours))::int, 'h ',
                            CASE
                                WHEN (SUM(h.total_hours) - FLOOR(SUM(h.total_hours))) < 0.01 THEN 0
                                ELSE ROUND((SUM(h.total_hours) - FLOOR(SUM(h.total_hours))) * 60)::int
                            END, 'min'
                        ) AS name,
                        'time_tracking' AS event_type,
                        h.employee_id,
                        e.user_id AS user_id,
                        DATE_TRUNC('day', h.datetime_start) AS datetime_start,
                        DATE_TRUNC('day', h.datetime_start) + INTERVAL '23 hours 59 minutes' AS datetime_end,
                        NULL::float AS time_tracking_start,
                        NULL::float AS time_tracking_end,
                        'kojto.hr.time.tracking' AS source_model,
                        NULL AS source_record_id,
                        NULL::integer AS subcode_id,
                        SUM(h.total_hours) AS total_hours,
                        NULL AS comment,
                        NULL::integer AS leave_type_id,
                        NULL AS reason,
                        NULL AS leave_status,
                        NULL::integer AS code_id,
                        NULL AS destination,
                        NULL AS business_purpose,
                        '#abcaee' AS color,
                        1 AS all_day,
                        0 AS create,
                        0 AS delete
                    FROM kojto_hr_time_tracking h
                    LEFT JOIN kojto_hr_employees e ON h.employee_id = e.id
                    {}
                    WHERE h.datetime_start IS NOT NULL AND h.datetime_end IS NOT NULL AND h.employee_id IS NOT NULL AND e.user_id IS NOT NULL
                    GROUP BY h.employee_id, DATE_TRUNC('day', h.datetime_start), e.user_id
                ) AS combined
            )
            """.format(
                self._table,
                fr_join_sql
            )
        )

    @api.model
    def create(self, vals_list):
        created_records = self.env[self._name]
        if not isinstance(vals_list, list):
            vals_list = [vals_list]

        for vals in vals_list:
            event_type = vals.get("event_type")

            if not event_type:
                _logger.warning("Missing event_type, skipping: %s", vals)
                continue

            try:
                if event_type == "time_tracking":
                    record = self._create_time_tracking_event(vals)
                elif event_type == "leave":
                    record = self._create_leave_event(vals)
                elif event_type == "business_trip":
                    record = self._create_business_trip_event(vals)
                else:
                    _logger.warning("Invalid event_type %s", event_type)
                    continue

                if record:
                    created_records |= record

            except ValidationError as e:
                _logger.error("Validation error creating %s event: %s", event_type, e)
                # Extract the user-friendly message from ValidationError
                error_message = str(e) if hasattr(e, 'name') and e.name else str(e)
                raise UserError(error_message)
            except UserError as e:
                _logger.error("User error creating %s event: %s", event_type, e)
                # Re-raise UserError as-is to preserve the user-friendly message
                raise
            except Exception as e:
                _logger.error("Unexpected error creating %s event: %s", event_type, e)
                raise UserError("An unexpected error occurred while creating the event. Please try again.")

        if not created_records:
            raise UserError("No calendar events were created. Please check your input data.")

        return created_records

    def _create_time_tracking_event(self, vals):
        source_model = "kojto.hr.time.tracking"

        if not vals.get("subcode_id"):
            _logger.warning("Missing subcode_id for time_tracking: %s", vals)
            return None

        # Make a copy to avoid modifying the original vals
        source_vals = vals.copy()
        # Update datetime fields from decimal time fields if present
        source_vals = self.update_datetimes_from_decimal(source_vals)
        # Prepare source values by filtering to only include fields in the source model
        source_vals = self._prepare_source_vals(source_vals, source_model)
        # Convert timezone
        source_vals = self._convert_timezone(source_vals)
        record = self.env[source_model].create(source_vals)

        return self._find_calendar_event(source_model, record.id)

    def _create_leave_event(self, vals):
        source_model = "kojto.hr.leave.management"

        if not vals.get("leave_type_id"):
            _logger.warning("Missing leave_type_id for leave: %s", vals)
            return None

        # Handle date-only display fields (from form UI) - convert directly to date_start/date_end
        date_from_display = False
        if "start_date_only_display" in vals:
            date_from_display = True
            if vals["start_date_only_display"]:
                # Convert date field directly to date_start
                if isinstance(vals["start_date_only_display"], str):
                    vals["date_start"] = fields.Date.from_string(vals["start_date_only_display"])
                else:
                    vals["date_start"] = vals["start_date_only_display"]
            else:
                vals["date_start"] = False
            # Remove the display field as it's not in the source model
            del vals["start_date_only_display"]

        if "end_date_only_display" in vals:
            date_from_display = True
            if vals["end_date_only_display"]:
                # Convert date field directly to date_end
                if isinstance(vals["end_date_only_display"], str):
                    vals["date_end"] = fields.Date.from_string(vals["end_date_only_display"])
                else:
                    vals["date_end"] = vals["end_date_only_display"]
            else:
                vals["date_end"] = False
            # Remove the display field as it's not in the source model
            del vals["end_date_only_display"]

        # Also handle datetime fields if they exist (fallback or from other sources)
        # Only convert datetime fields if we didn't already set dates from display fields
        if not date_from_display:
            converted_vals = self._convert_datetime_to_date_fields(vals.copy())
        else:
            # Still need to remove datetime fields if they exist, but don't convert them
            converted_vals = vals.copy()
            converted_vals.pop("datetime_start", None)
            converted_vals.pop("datetime_end", None)

        source_vals = self._prepare_source_vals(converted_vals, source_model)
        source_vals["leave_status"] = "pending"

        record = self.env[source_model].create(source_vals)

        return self._find_calendar_event(source_model, record.id)

    def _create_business_trip_event(self, vals):
        source_model = "kojto.hr.business.trips"

        if not vals.get("code_id"):
            _logger.warning("Missing code_id for business_trip: %s", vals)
            return None

        converted_vals = self._convert_datetime_to_date_fields(vals.copy())
        source_vals = self._prepare_source_vals(converted_vals, source_model)

        record = self.env[source_model].create(source_vals)

        return self._find_calendar_event(source_model, record.id)

    def _prepare_source_vals(self, vals, source_model):
        excluded_fields = {"id", "event_type", "source_model", "source_record_id", "user_id"}
        return {
            key: vals[key]
            for key in self.env[source_model]._fields
            if key in vals and key not in excluded_fields
        }

    def _convert_timezone(self, source_vals):
        if not source_vals:  # Add this check
            return source_vals

        user_tz = pytz.timezone(self.env.user.tz or "UTC")

        for dt_field in ("datetime_start", "datetime_end"):
            if dt_field in source_vals and source_vals[dt_field]:
                try:
                    dt = fields.Datetime.from_string(source_vals[dt_field])

                    if dt.tzinfo:
                        utc_dt = dt.astimezone(pytz.utc).replace(tzinfo=None)
                        source_vals[dt_field] = fields.Datetime.to_string(utc_dt)
                    else:
                        local_dt = user_tz.localize(dt)
                        utc_dt = local_dt.astimezone(pytz.utc).replace(tzinfo=None)
                        source_vals[dt_field] = fields.Datetime.to_string(utc_dt)

                except ValueError as e:
                    _logger.warning("Invalid datetime format for %s: %s - Error: %s", dt_field, source_vals[dt_field], e)
                    continue  # Skip invalid datetime

        return source_vals

    def _convert_datetime_to_date_fields(self, vals, mappings=None):
        """
        Utility method to convert datetime fields (e.g., datetime_start) into corresponding
        date fields (e.g., date_start). Operates in-place on the provided vals dict.
        """
        if not isinstance(vals, dict):
            return vals

        mappings = mappings or (("datetime_start", "date_start"), ("datetime_end", "date_end"))

        for datetime_field, date_field in mappings:
            if datetime_field not in vals:
                continue

            datetime_value = vals.pop(datetime_field)
            if not datetime_value:
                vals[date_field] = False
                continue

            dt = datetime_value
            if not isinstance(datetime_value, datetime):
                dt = fields.Datetime.from_string(datetime_value)

            vals[date_field] = dt.date() if dt else False

        return vals

    def _find_calendar_event(self, source_model, record_id):
        calendar_event = self.search([
            ("source_model", "=", source_model),
            ("source_record_id", "=", record_id)
        ], limit=1)

        if not calendar_event:
            _logger.warning("No calendar event found for record ID %s in %s", record_id, source_model)
            return None

        return calendar_event


    def write(self, vals):
        for record in self:
            if not record.source_record_id:
                continue

            source_record = self.env[record.source_model].browse(record.source_record_id)
            modified_vals = vals.copy()

            if record.event_type == 'time_tracking' and ('time_tracking_start' in vals or 'time_tracking_end' in vals):
                modified_vals = self.update_datetimes_from_decimal(modified_vals, record.datetime_start)
                modified_vals = self._convert_timezone(modified_vals)

            if record.event_type == 'time_tracking':
                datetime_start = modified_vals.get("datetime_start") or source_record.datetime_start
                datetime_end = modified_vals.get("datetime_end") or source_record.datetime_end
                if "datetime_start" in modified_vals and "datetime_end" in modified_vals:
                    # Both present, can swap if needed
                    start_dt = fields.Datetime.from_string(datetime_start) if isinstance(datetime_start, str) else datetime_start
                    end_dt = fields.Datetime.from_string(datetime_end) if isinstance(datetime_end, str) else datetime_end
                    if start_dt and end_dt and start_dt > end_dt:
                        modified_vals["datetime_start"], modified_vals["datetime_end"] = modified_vals["datetime_end"], modified_vals["datetime_start"]
                elif "datetime_start" in modified_vals or "datetime_end" in modified_vals:
                    # Only one present, check if the result would be invalid
                    start_dt = fields.Datetime.from_string(datetime_start) if isinstance(datetime_start, str) else datetime_start
                    end_dt = fields.Datetime.from_string(datetime_end) if isinstance(datetime_end, str) else datetime_end
                    if start_dt and end_dt and start_dt > end_dt:
                        raise UserError("Start time cannot be after end time. Please correct your input.")

            if record.event_type == 'leave':
                # Handle date-only display fields (from form UI) - convert directly to date_start/date_end
                date_from_display = False
                if "start_date_only_display" in modified_vals:
                    date_from_display = True
                    if modified_vals["start_date_only_display"]:
                        # Convert date field directly to date_start
                        if isinstance(modified_vals["start_date_only_display"], str):
                            modified_vals["date_start"] = fields.Date.from_string(modified_vals["start_date_only_display"])
                        else:
                            modified_vals["date_start"] = modified_vals["start_date_only_display"]
                    else:
                        modified_vals["date_start"] = False
                    # Remove the display field as it's not in the source model
                    del modified_vals["start_date_only_display"]

                if "end_date_only_display" in modified_vals:
                    date_from_display = True
                    if modified_vals["end_date_only_display"]:
                        # Convert date field directly to date_end
                        if isinstance(modified_vals["end_date_only_display"], str):
                            modified_vals["date_end"] = fields.Date.from_string(modified_vals["end_date_only_display"])
                        else:
                            modified_vals["date_end"] = modified_vals["end_date_only_display"]
                    else:
                        modified_vals["date_end"] = False
                    # Remove the display field as it's not in the source model
                    del modified_vals["end_date_only_display"]

                # Also handle datetime fields if they exist (fallback or from other sources)
                # Only convert datetime fields if we didn't already set dates from display fields
                if not date_from_display:
                    modified_vals = self._convert_datetime_to_date_fields(modified_vals)
                else:
                    # Still need to remove datetime fields if they exist, but don't convert them
                    modified_vals.pop("datetime_start", None)
                    modified_vals.pop("datetime_end", None)

            if record.event_type == 'business_trip':
                modified_vals = self._convert_datetime_to_date_fields(modified_vals)

            source_vals = {
                key: modified_vals[key]
                for key in source_record._fields
                if key in modified_vals and key not in ("id", "event_type", "source_model", "source_record_id", "user_id")
            }

            try:
                if source_vals:
                    source_record.write(source_vals)
            except ValidationError as e:
                _logger.error("Validation error updating record in %s: %s", record.source_model, e)
                # Extract the user-friendly message from ValidationError
                error_message = str(e) if hasattr(e, 'name') and e.name else str(e)
                raise UserError(error_message)
            except UserError as e:
                _logger.error("User error updating record in %s: %s", record.source_model, e)
                # Re-raise UserError as-is to preserve the user-friendly message
                raise
            except Exception as e:
                _logger.error("Unexpected error updating record in %s: %s", record.source_model, e)
                raise UserError("An unexpected error occurred while updating the record. Please try again.")

        return True

    def unlink(self):
        for record in self:
            if not record.source_record_id:
                continue

            try:
                source_record = self.env[record.source_model].browse(record.source_record_id)
                source_record.unlink()
            except ValidationError as e:
                _logger.error("Validation error deleting record in %s: %s", record.source_model, e)
                # Extract the user-friendly message from ValidationError
                error_message = str(e) if hasattr(e, 'name') and e.name else str(e)
                raise UserError(error_message)
            except UserError as e:
                _logger.error("User error deleting record in %s: %s", record.source_model, e)
                # Re-raise UserError as-is to preserve the user-friendly message
                raise
            except Exception as e:
                _logger.error("Unexpected error deleting record in %s: %s", record.source_model, e)
                raise UserError("An unexpected error occurred while deleting the record. Please try again.")
        return True

    def update_datetimes_from_decimal(self, data, base_date=None):
        if 'time_tracking_start' not in data and 'time_tracking_end' not in data:
            return data

        if not base_date:
            # Prefer an explicit date from the incoming data
            try:
                if data.get('datetime_start'):
                    if isinstance(data['datetime_start'], str):
                        base_date = datetime.strptime(data['datetime_start'], '%Y-%m-%d %H:%M:%S').date()
                    elif isinstance(data['datetime_start'], datetime):
                        base_date = data['datetime_start'].date()
                elif data.get('date'):
                    # Allow plain date to be passed (YYYY-MM-DD)
                    base_date = fields.Date.from_string(data['date'])
                else:
                    # Next, look at context-supplied defaults (e.g., selected calendar day)
                    ctx = self.env.context or {}
                    if ctx.get('default_date'):
                        base_date = fields.Date.from_string(ctx.get('default_date'))
                    elif ctx.get('default_datetime_start'):
                        dt_start = fields.Datetime.from_string(ctx.get('default_datetime_start'))
                        base_date = dt_start.date() if dt_start else None
            except Exception:
                base_date = None

            # Final fallback: use record's own date or today's date
            if not base_date:
                base_date = self.datetime_start.date() if getattr(self, 'datetime_start', None) else datetime.now().date()

        def decimal_to_time_precise(decimal_hours):
            decimal_hours = round(decimal_hours * 60) / 60

            hours = int(decimal_hours)
            minutes = round((decimal_hours - hours) * 60)

            if minutes >= 60:
                hours += 1
                minutes = 0

            return hours, minutes

        if 'time_tracking_start' in data:
            hours, minutes = decimal_to_time_precise(data['time_tracking_start'])
            new_datetime = datetime.combine(base_date, datetime.min.time()) + timedelta(hours=hours, minutes=minutes)
            data['datetime_start'] = new_datetime.strftime('%Y-%m-%d %H:%M:%S')

        if 'time_tracking_end' in data:
            hours, minutes = decimal_to_time_precise(data['time_tracking_end'])
            new_datetime = datetime.combine(base_date, datetime.min.time()) + timedelta(hours=hours, minutes=minutes)
            data['datetime_end'] = new_datetime.strftime('%Y-%m-%d %H:%M:%S')

        return data


    @api.depends('datetime_start')
    def _compute_time_tracking_start(self):
        for record in self:
            if record.datetime_start:
                local_dt = fields.Datetime.context_timestamp(record, record.datetime_start)
                record.time_tracking_start = local_dt.hour + local_dt.minute / 60.0
            else:
                record.time_tracking_start = 0.0

    @api.depends('datetime_end')
    def _compute_time_tracking_end(self):
        for record in self:
            if record.datetime_end:
                local_dt = fields.Datetime.context_timestamp(record, record.datetime_end)
                record.time_tracking_end = local_dt.hour + local_dt.minute / 60.0
            else:
                record.time_tracking_end = 0.0


    def _inverse_time_tracking_start(self):
        for record in self:
            if record.datetime_start and record.time_tracking_start is not False:
                local_dt = fields.Datetime.context_timestamp(record, record.datetime_start)
                base_date = local_dt.date()

                hours = int(record.time_tracking_start)
                minutes = int((record.time_tracking_start - hours) * 60)

                new_local_dt = datetime.combine(base_date, time(hours, minutes))

                user_tz = pytz.timezone(self.env.user.tz or 'UTC')
                local_dt_with_tz = user_tz.localize(new_local_dt)
                utc_dt = local_dt_with_tz.astimezone(pytz.UTC)

                record.datetime_start = utc_dt.replace(tzinfo=None)

    def _inverse_time_tracking_end(self):
        for record in self:
            if record.datetime_end and record.time_tracking_end is not False:
                local_dt = fields.Datetime.context_timestamp(record, record.datetime_end)
                base_date = local_dt.date()

                hours = int(record.time_tracking_end)
                minutes = int((record.time_tracking_end - hours) * 60)

                new_local_dt = datetime.combine(base_date, time(hours, minutes))

                user_tz = pytz.timezone(self.env.user.tz or 'UTC')
                local_dt_with_tz = user_tz.localize(new_local_dt)
                utc_dt = local_dt_with_tz.astimezone(pytz.UTC)

                record.datetime_end = utc_dt.replace(tzinfo=None)

    @api.model
    def default_get(self, fields_list):
        """Override to set default employee_id from selected calendar filters"""
        defaults = super().default_get(fields_list)

        if 'employee_id' in fields_list and not defaults.get('employee_id'):
            if self.env.context.get('default_employee_id'):
                defaults['employee_id'] = self.env.context.get('default_employee_id')
            else:
                filter_model = self.env['kojto.hr.calendar.filters']
                first_checked_employee = filter_model.get_checked_employee()

                if first_checked_employee:
                    defaults['employee_id'] = first_checked_employee
                elif self.env.user.employee:
                    defaults['employee_id'] = self.env.user.employee.id

        return defaults

    @api.model
    def get_unusual_days(self, start_date, end_date):
        start = fields.Date.from_string(start_date)
        end = fields.Date.from_string(end_date)

        non_working_days = self.env['kojto.hr.working.days'].search([
            ('date', '>=', start),
            ('date', '<=', end),
            ('day_type', 'in', ['weekend', 'public_holiday'])
        ])

        unusual_days = {}

        for record in non_working_days:
            date_str = record.date.isoformat()
            unusual_days[date_str] = {
                'is_unusual': True,
                'title': record.display_name or dict(self._fields['day_type'].selection).get(record.day_type),
                'day_type': record.day_type,
                'is_working_day': record.is_working_day
            }

        return unusual_days

    def _get_default_time_tracking_start(self):
        employee_id = self.env.context.get('default_employee_id')
        if not employee_id:
            filter_model = self.env['kojto.hr.calendar.filters']
            employee_id = filter_model.get_checked_employee()
            if not employee_id and self.env.user.employee:
                employee_id = self.env.user.employee.id

        if not employee_id:
            return 8.0

        current_date = datetime.now().date()
        if self.env.context.get('default_date'):
            current_date = fields.Date.from_string(self.env.context.get('default_date'))
        elif self.env.context.get('default_datetime_start'):
            dt_start = fields.Datetime.from_string(self.env.context.get('default_datetime_start'))
            current_date = dt_start.date()

        latest_entry = self.env['kojto.hr.time.tracking'].search([
            ('employee_id', '=', employee_id),
            ('datetime_start', '>=', datetime.combine(current_date, datetime.min.time())),
            ('datetime_start', '<', datetime.combine(current_date + timedelta(days=1), datetime.min.time())),
            ('datetime_end', '!=', False)
        ], order='datetime_end desc', limit=1)

        if not latest_entry:
            return 8.0

        user_tz = pytz.timezone(self.env.user.tz or 'UTC')
        end_time_local = pytz.utc.localize(latest_entry.datetime_end).astimezone(user_tz)

        return end_time_local.hour + end_time_local.minute / 60.0

    def _get_default_time_tracking_end(self):
        start_time = self._get_default_time_tracking_start()

        if start_time is False:
            return False

        if start_time >= 16.0:
            return start_time+1.0

        return 16.0

    def _compute_fr_times(self):
        try:
            FaceRec = self.env['kojto.hr.face.recognition'].sudo()
        except KeyError:
            for rec in self:
                rec.face_recognition_times_display = False
            return
        for rec in self:
            rec.face_recognition_times_display = False
            if not rec.employee_id or not rec.datetime_start:
                continue
            day_start = datetime.combine(rec.datetime_start.date(), datetime.min.time())
            day_end = datetime.combine(rec.datetime_start.date(), datetime.max.time())
            frs = FaceRec.search([
                ('employee_id', '=', rec.employee_id.id),
                ('datetime_taken', '>=', fields.Datetime.to_string(day_start)),
                ('datetime_taken', '<=', fields.Datetime.to_string(day_end)),
            ], order='datetime_taken asc')
            if not frs:
                continue
            times = [fields.Datetime.context_timestamp(rec, fr.datetime_taken).strftime('%H:%M') for fr in frs if fr.datetime_taken]
            rec.face_recognition_times_display = ', '.join(times)
