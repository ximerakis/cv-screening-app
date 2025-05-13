import streamlit as st
import fitz  # PyMuPDF
import pandas as pd
from openai import OpenAI
import tempfile
import re

import smtplib
from email.mime.text import MIMEText

def send_email(to_email, subject, body, from_email, app_password):
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = from_email
    msg['To'] = to_email

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(from_email, app_password)
        server.send_message(msg)


st.title("📄 CV Screening Assistant")

api_key = st.text_input("🔐 Enter your OpenAI API Key", type="password")
client = OpenAI(api_key=api_key)
st.subheader("📤 Email Configuration")
gmail_address = st.text_input("Your Gmail address (sender)", type="default")
gmail_password = st.text_input("Gmail App Password", type="password")


jd_file = st.file_uploader("📌 Upload Job Description (PDF or TXT)", type=["pdf", "txt"])
cv_files = st.file_uploader("📎 Upload Candidate CVs (PDF)", type="pdf", accept_multiple_files=True)
excel_file = st.file_uploader("📋 Upload Excel file with candidate emails", type=["xlsx"])

if st.button("▶️ Run Screening") and jd_file and cv_files and excel_file and api_key:
    st.info("Processing...")

    # Read job description
    if jd_file.name.endswith(".pdf"):
        with fitz.open(stream=jd_file.read(), filetype="pdf") as doc:
            job_description = "\n".join(page.get_text() for page in doc)
    else:
        job_description = jd_file.read().decode("utf-8")

    # Read email mapping
    df_emails = pd.read_excel(excel_file)
    email_lookup = dict(zip(df_emails['filename'], df_emails['email']))

    results = []

    for cv_file in cv_files:
        filename = cv_file.name

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            cv_bytes = cv_file.read()
            tmp.write(cv_bytes)
            tmp.flush()  # ensure data is written
            doc = fitz.open(tmp.name)
            cv_text = "\n".join(page.get_text() for page in doc)
            doc.close()


        prompt = f"""
Compare this CV to the job description below.
Return only a match percentage (0–100) and a short explanation.

Job Description:
{job_description}

CV:
{cv_text}

Respond in this format:
Match Percentage: XX%
Explanation: ...
"""

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful HR assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=500
        )

        result_text = response.choices[0].message.content
        match = re.search(r"Match Percentage:\s*(\d+)", result_text)
        score = int(match.group(1)) if match else None
        explanation = result_text.split("Explanation:")[-1].strip() if "Explanation:" in result_text else "N/A"
        email = email_lookup.get(filename, "Not found")
        status = "Passed" if score and score >= 85 else "Not Passed"

        # Send result email if address is found
        if email != "Not found" and gmail_address and gmail_password:
            if score is not None and score >= 85:
                subject = "🎉 Next Step in Your Application"
                body = (
                    f"Dear Candidate,\n\n"
                    f"Congratulations! Based on your CV, you've passed to the next step in our recruitment process.\n\n"
                    f"Match Score: {score}%\n\n"
                    f"Best regards,\nHR Team"
                )
            else:
                subject = "Thank You for Applying"
                body = (
                    f"Dear Candidate,\n\n"
                    f"Thank you for applying. Unfortunately, your profile did not meet the criteria for this position.\n\n"
                    f"Match Score: {score if score else 'N/A'}%\n\n"
                    f"Kind regards,\nHR Team"
                )
        
            try:
                send_email(email, subject, body, gmail_address, gmail_password)
                st.info(f"📧 Email sent to {email}")
            except Exception as e:
                st.error(f"❌ Failed to send email to {email}: {e}")


        results.append({
            "Filename": filename,
            "Email": email,
            "Score": score,
            "Status": status,
            "Explanation": explanation
        })

    df_results = pd.DataFrame(results)
    st.success("✅ Screening complete.")
    st.dataframe(df_results)
    st.download_button("📥 Download Results", df_results.to_csv(index=False), "cv_screening_results.csv")


