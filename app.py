from flask import Flask, request, send_file, render_template_string
import pdfplumber
import re
from datetime import datetime
from ics import Calendar, Event
import pytz
import io

app = Flask(__name__)

# Global storage for parsed schedules
parsed_schedules = {}

HTML_UPLOAD_FORM = """
<!doctype html>
<title>Upload Schedule</title>
<h1>Upload Schedule PDF</h1>
<form method=post enctype=multipart/form-data>
  <input type=file name=file required>
  <br><br>
  <input type=submit value="Parse Schedule">
</form>
"""

HTML_SELECT_FORM = """
<!doctype html>
<title>Select Name</title>
<h1>Select Your Name</h1>
<form method=post>
  <select name="lastname" required>
    {% for name in names %}
      <option value="{{ name }}">{{ name }}</option>
    {% endfor %}
  </select>
  <br><br>
  <input type=submit value="Generate ICS">
</form>
"""

@app.route("/", methods=["GET", "POST"])
def upload_file():
    global parsed_schedules
    if request.method == "POST" and "file" in request.files:
        file = request.files["file"]

        # Extract text from PDF
        text = ""
        with pdfplumber.open(file) as pdf:
            for page in pdf.pages:
                text += page.extract_text() + "\n"

        # Extract dates from header
        date_line = re.search(r'Associates.*', text)
        if not date_line:
            return "Could not find the date header line."
        date_matches = re.findall(r'(\d{2}/\d{2})', date_line.group())
        dates = [datetime.strptime(f"{d}/2025", "%m/%d/%Y") for d in date_matches]

        # Extract all names and schedules
        rows = re.findall(r'([A-Z]+, [A-Z]+(?: [A-Z]+)?)\s+(.*?)\s+(?=\w+, \w+|$)', text)
        parsed_schedules = {}
        for name, shifts_raw in rows:
            tokens = shifts_raw.strip().split()
            shifts = []
            i = 0
            while len(shifts) < len(dates) and i < len(tokens):
                if tokens[i] == "OFF":
                    shifts.append("OFF")
                    i += 1
                elif i + 4 < len(tokens) and tokens[i+2] == "-":
                    shift = f"{tokens[i]} {tokens[i+1]} - {tokens[i+3]} {tokens[i+4]}"
                    shifts.append(shift)
                    i += 5
                else:
                    i += 1
            parsed_schedules[name] = [(date, shift) for date, shift in zip(dates, shifts) if shift != "OFF"]

        # Show dropdown
        return render_template_string(HTML_SELECT_FORM, names=parsed_schedules.keys())

    elif request.method == "POST" and "lastname" in request.form:
        lastname = request.form.get("lastname")
        schedule = parsed_schedules.get(lastname)
        if not schedule:
            return f"No schedule found for {lastname}."

        # Create ICS file
        tz = pytz.timezone("America/Chicago")
        calendar = Calendar()
        for date_obj, shift in schedule:
            start_str, end_str = shift.split(" - ")
            start_time = datetime.strptime(start_str, "%I:%M %p").time()
            end_time = datetime.strptime(end_str, "%I:%M %p").time()

            start_dt = tz.localize(datetime.combine(date_obj.date(), start_time))
            end_dt = tz.localize(datetime.combine(date_obj.date(), end_time))

            event = Event()
            event.name = "Work Shift"
            event.begin = start_dt
            event.end = end_dt
            event.location = "U of Ark-Catering"
            calendar.events.add(event)

        # Return ICS file
        ics_file = io.StringIO()
        ics_file.writelines(calendar)
        ics_file.seek(0)

        return send_file(io.BytesIO(ics_file.getvalue().encode()),
                         mimetype="text/calendar",
                         as_attachment=True,
                         download_name=f"{lastname}_schedule.ics")

    return render_template_string(HTML_UPLOAD_FORM)

if __name__ == "__main__":
    app.run(debug=True)
