from flask import Flask, request, send_file, render_template_string
import pdfplumber
import re
from datetime import datetime, timedelta
from ics import Calendar, Event
import pytz
import io

app = Flask(__name__)

HTML_FORM = """
<!doctype html>
<title>Upload Schedule</title>
<h1>Upload Your Schedule PDF</h1>
<form method=post enctype=multipart/form-data>
  <input type=file name=file>
  <input type=submit value="Generate ICS">
</form>
"""

@app.route("/", methods=["GET", "POST"])
def upload_file():
    if request.method == "POST":
        file = request.files["file"]

        # Extract text from PDF
        text = ""
        with pdfplumber.open(file) as pdf:
            for page in pdf.pages:
                text += page.extract_text() + "\n"

        # Step 1: Extract the date range from the header
        date_line = re.search(r'Associates.*', text)
        if not date_line:
            return "Could not find the date header line."

        # Extract MM/DD dates from the header
        date_matches = re.findall(r'(\d{2}/\d{2})', date_line.group())
        dates = [datetime.strptime(f"{d}/2025", "%m/%d/%Y") for d in date_matches]

        # Step 2: Extract Chance Pickett's line
        match = re.search(r'PICKETT, CHANCE\s+(.*)', text)
        if not match:
            return "Could not find schedule for PICKETT, CHANCE."

        # Step 3: Tokenize and group shift entries
        tokens = match.group(1).strip().split()
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
                i += 1  # Skip malformed entries

        # Step 4: Pair dates with shifts, excluding OFF days
        if len(shifts) != len(dates):
            return "Mismatch between number of dates and shift entries."

        schedule = [(date, shift) for date, shift in zip(dates, shifts) if shift != "OFF"]

        # Set timezone
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
                         download_name="work_schedule.ics")

    return render_template_string(HTML_FORM)

if __name__ == "__main__":
    app.run(debug=True)