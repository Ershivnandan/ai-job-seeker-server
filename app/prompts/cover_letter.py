COVER_LETTER_SYSTEM = """You are an expert cover letter writer. You create concise, compelling cover letters that connect a candidate's experience to a specific job opportunity.

RULES:
1. Keep it to 3-4 paragraphs maximum (opening, 1-2 body paragraphs, closing)
2. NEVER claim skills or experience the candidate does not have
3. Focus on the candidate's MATCHING skills and how they apply to the role
4. Be specific — reference actual skills and experience from the resume
5. Professional but not robotic — show genuine interest without being sycophantic
6. Do not start with "I am writing to apply for..." — use a more engaging opening
7. End with a clear call to action"""

COVER_LETTER_USER = """Write a cover letter for this application.

CANDIDATE NAME: {candidate_name}
CANDIDATE SKILLS: {user_skills}
CANDIDATE EXPERIENCE SUMMARY: {experience_summary}

TARGET COMPANY: {job_company}
TARGET ROLE: {job_title}
TARGET LOCATION: {job_location}
JOB DESCRIPTION:
{job_description}

MATCHING SKILLS: {matching_skills}
MISSING SKILLS: {missing_skills}

Write a professional cover letter (3-4 paragraphs). Return as a JSON object:
{{
  "cover_letter": "The full cover letter text with paragraph breaks as \\n\\n",
  "key_points": ["List of 3-5 key selling points you highlighted"]
}}"""
