import streamlit as st
import fitz  # PyMuPDF
import pandas as pd
from openai import OpenAI
import tempfile
import re

st.title("📄 CV Screening Assistant")

api_key = st.text_input("🔐 Enter your OpenAI API Key", type="password")
client = OpenAI(api_key=api_key)


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


