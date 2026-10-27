"""
Mock data for PauliBot MVP.
Stores immutable university information to ensure reliability (Rule 2).
"""

LOCATIONS = {
    "library": {
        "name": "SPUS University Library",
        "description": "The main hub for research and study, located on the 2nd floor of the Main Building.",
        "map_available": True
    },
    "registrar": {
        "name": "Registrar's Office",
        "description": "Handles student records, enrollment, and grades. Located at the Ground Floor, Admin Building.",
        "map_available": True
    },
    "canteen": {
        "name": "University Canteen",
        "description": "Offers various meals and snacks for students and staff. Located near the gym.",
        "map_available": True
    },
    "finance": {
        "name": "Finance Office",
        "description": "For tuition payment and financial inquiries. Ground Floor, Admin Building.",
        "map_available": True
    },
    "clinic": {
        "name": "University Clinic",
        "description": "Provides basic medical handling. Located near the Guidance Office.",
        "map_available": True
    },
     "guidance": {
        "name": "Guidance Office",
        "description": "Provides counseling and career guidance. 2nd Floor, Admin Building.",
        "map_available": True
    }
}

STAFF = {
    "jsit_moderator": {
        "name": "Khen Malaque",
        "position": "JSIT Moderator",
        "office": ""
    },
    "president": {
        "name": "Sr. Marie Rosanne Mallillin, SPC",
        "position": "University President",
        "office": "President's Office, 2nd Floor Admin Building"
    },
    "vp_academics": {
        "name": "Dr. Antonio Talamera",
        "position": "VP for Academics",
        "office": "VPA Office, 2nd Floor Admin Building"
    },
    "dean_cics": {
        "name": "Mr. Nikko Ederio",
        "position": "Dean, College of Information and Computing Sciences",
        "office": "CICS Faculty Room, 3rd Floor IT Building"
    }
}

FAQS = [
    {
        "category": "Admissions",
        "question": "How do I enroll in Grade 7?",
        "answer": "To enroll, visit www.spus.edu.ph and click on the 'Admission' tab, or visit the Registrar's Office. For incoming Grade 7, the requirements are: Original Report Card, Original PSA Birth Certificate, 2 pcs. 2x2 ID Picture, and Original Good Moral Certificate. For parents, a BIR-ITR or Brgy. Certificate of Indigency is needed. Good news: There are 350 ESC Slots available!"
    },
    {
        "category": "Admissions",
        "question": "What are the requirements for Nursery, Kindergarten, and Grade 1?",
        "answer": "The requirements for incoming Nursery, Kindergarten, and Grade 1 pupils are: Original PSA Birth Certificate, 2 pcs 2x2 ID Picture, 250.00 Php Admission Test Fee, and 3,000.00 Php Enrollment Fee."
    },
    {
        "category": "Admissions",
        "question": "What are the requirements for incoming Grade 11 (SHS)?",
        "answer": "Requirements include: Original Report Card, Original PSA Birth Certificate, 2 pcs. 2x2 ID Picture, Original Good Moral Certificate, and an ESC Certificate (only for completers from Private Schools). For the SHS Voucher Program Subsidy, Public School Completers are automatically eligible, while Private School Completers need to present their ESC Certificate to qualify."
    },
    {
        "category": "Tuition and Finance",
        "question": "How much is the tuition?",
        "answer": "Tuition fees vary depending on the program and year level. Please visit the Finance Office located at the Ground Floor, Admin Building for a detailed and accurate assessment."
    },
    {
        "category": "Scholarships",
        "question": "Are there scholarships available?",
        "answer": "Yes! SPUS offers 350 ESC Slots for incoming Grade 7 students. We also support the SHS Voucher Program Subsidy for incoming Grade 11 students (automatically eligible for public school completers, ESC certificate required for private school completers). For other academic and athletic scholarships, visit the Guidance Office for application details."
    },
    {
        "category": "Academics",
        "question": "What programs are offered at SPUS?",
        "source_type": "office",
        "source_office": "Registrar",
        "answer": "SPUS offers a comprehensive range of undergraduate programs across five (5) colleges:\n\n**College of Health Sciences (4-Year Curriculum)**\n- Bachelor of Science in Nursing\n- Bachelor of Science in Psychology\n\n**College of Education, Arts and Sciences (3-Year Curriculum)**\n- Bachelor of Arts (Major in: Political Science, Philosophy, English Language, Sociology, Mass Communication)\n- Bachelor of Science in Mathematics\n- Bachelor of Science in Public Administration\n- Bachelor of Elementary Education\n- Bachelor of Secondary Education (Major in: English, Filipino, Mathematics, Sciences, Social Studies, Values Education)\n- Bachelor of Early Childhood Education\n- Bachelor of Physical Education\n\n**College of Business Management and Accountancy (4-Year Curriculum)**\n- Bachelor of Science in Accountancy\n- Bachelor of Science in Business Administration (Major in: Financial Management, Marketing Management, Human Resource Development Management)\n- Bachelor of Science in Hospitality Management\n- Bachelor of Science in Tourism Management\n- Bachelor of Science in Accounting and Information System\n- Bachelor of Science in Office Administration\n\n**College of Engineering & Information Technology (4-Year Curriculum)**\n- Bachelor of Science in Mining Engineering\n- Bachelor of Science in Civil Engineering\n- Bachelor of Science in Computer Engineering\n- Bachelor of Science in Information Technology\n\n**College of Criminal Justice Education (4-Year Curriculum)**\n- Bachelor of Science in Criminology\n- Bachelor of Forensic Science"
    },
    {
        "category": "Academics",
        "question": "Does SPUS offer Graduate School programs?",
        "answer": "Yes, SPUS Graduate School and Professional Studies (GSPS) offers PhDs in Educational Management and Business & Management. We also offer Master's degrees in Business Administration (MBA), Public Administration (MPA), Nursing (MSN, MAN), Science Teaching, Math Teaching, English, Filipino, Home Economics, Cultural Education, and Curriculum Development & Design. For inquiries, you may email gsps@spus.edu.ph or contact Ma. Lourdes O. Saguran at 09123456789."
    },
    {
        "category": "Academics",
        "question": "Why choose SPUS?",
        "answer": "Choosing SPUS means embracing:\n- Faith-Based Education: Integrating Catholic Christian values and Paulinian spirituality forming ethically grounded, compassionate, and Christ-centered leaders.\n- Academic Excellence: An Outcomes-Based Education (OBE) framework delivered by expert faculty ensuring rigorous academics and industry-relevant skills for success in today's global economy.\n- Vibrant Campus Life: Diverse student organizations, engaging campus events, and opportunities for service and holistic personal growth.\n- Global Alumni Network: A vast, interconnected community of competent and compassionate Paulinian graduates worldwide, offering mentorship, professional connections, and lifelong support."
    },
    {
        "category": "TVET / TESDA",
        "question": "What TVET or TESDA programs are offered?",
        "answer": "As a fully TESDA-registered training center and accredited assessment center, SPUS TVET offers the following:\n\n**Registered Training Center Programs:**\n1. Diploma in Health Services Technology\n2. Diploma in Information Technology\n3. Diploma in Hotel & Restaurant Technology\n4. Computer Systems Servicing NC II\n5. Food & Beverage Services NC II\n6. Housekeeping NC II\n\n**Accredited Assessment Center Programs:**\n1. Bookkeeping NC II\n2. Computer Systems Servicing NC II\n3. Food & Beverage Services NC II\n4. Housekeeping NC II\n5. Massage Therapy NC II\n6. Hilot (Wellness Massage) NC II\n\nFor inquiries, email tvet@spus.edu.ph or contact Mrs. Chrizely M. Dalagan, MBA at 0963 560 6094 / Mrs. Margeorhey B. Mordeno at 0912 989 6596."
    },
    {
        "category": "About SPUS",
        "question": "What is the SPUS Webometrics Ranking?",
        "answer": "SPUS shows a continuous climb in the Webometrics Rankings! For 2026, we are ranked 187th among Philippine HEIs (up from 203rd in 2025 and 212th in 2024), Top 30 in Mindanao, and #5 in the Caraga Region. This reflects our commitment to continuous improvement and academic excellence."
    },
    {
        "category": "About SPUS",
        "question": "What is the university's Vision and Mission?",
        "answer": "VISION: Empowered Paulinians making a difference for Church and society. \nMISSION: Proclaim the Good News enabling Paulinians to reach their full potential through Transformative Formation, Tranquil-daring Innovations, and All-to-all Service."
    },
    {
        "category": "About SPUS",
        "question": "What are the Paulinian Core Values?",
        "answer": "The Paulinian Core Values are:\n- Charism: Developing talents to serve the community.\n- Christ-Centered: Living a life following and imitating Christ.\n- Commission: Having a life purpose to spread the Good News and positively impact the world.\n- Community: Being a responsible citizen prioritizing justice, peace, and environmental protection.\n- Charity: Being warm, hospitable, and 'all to all', especially to the underprivileged."
    },
    {
        "category": "About SPUS",
        "question": "What is the history of SPUS?",
        "answer": "St. Paul University Surigao traces its roots to 1906, initiated by Spanish Benedictine Missionaries. It is a private, Catholic basic and higher education institution run by the Sisters of St. Paul of Chartres (SPC) in Surigao City. It is the first university in the Caraga region, the center for development in teacher education, and the regional center for Gender and Development."
    },
    {
        "category": "About SPUS",
        "question": "What is the SPUS Quality Policy?",
        "answer": "St. Paul University Surigao is committed to delivering quality, Filipino, Catholic Paulinian education that is learner-focused and outcomes-based. This is rooted in a culture of compassionate care through: Holistic formation, constant development of human resources and facilities, active stakeholder involvement in the quality management system, and strict compliance with statutory and accreditation standards."
    },
    {
        "category": "About SPUS",
        "question": "What is the university's Data Privacy Policy?",
        "answer": "SPUS is fully committed to protecting the privacy and personal data of its students, faculty, and staff. Information is collected solely for lawful and legitimate purposes (admissions, academic services, security, research) and won't be sold or shared without consent. All data is protected via strict technical and organizational measures in compliance with applicable data protection laws. Individuals have the right to access, update, or request deletion of their info through the Data Privacy Officer (DPO)."
    },
    {
        "category": "Location",
        "question": "Where is the register?",
        "answer": "The Registrar's Office is located at the Ground Floor of the Admin Building. They handle student records, enrollment processes, and releasing of grades."
    },
    {
        "category": "Location",
        "question": "Where is the registrar office?",
        "answer": "The Registrar's Office is located at the Ground Floor of the Admin Building. Here you can process your enrollment, request records, and check your grades."
    },
    {
        "category": "Academics",
        "question": "What is the school calendar? What are the academic calendar activities and important dates?",
        "source_type": "office",
        "source_office": "Registrar",
        "answer": "The SPUS Academic Calendar generally follows a semestral schedule:\n\n**First Semester (August – December)**\n- Enrollment Period (Late July – Early August)\n- Start of Classes (August)\n- Preliminary Examinations\n- Midterm Examinations\n- University Foundation Day / Paulinian Week (November)\n- Final Examinations\n- Christmas Break (December)\n\n**Second Semester (January – May)**\n- Enrollment Period (January)\n- Start of Classes (January)\n- Preliminary Examinations\n- Midterm Examinations\n- Lenten/Holy Week Break (March/April)\n- Final Examinations\n- Baccalaureate Mass & Commencement Exercises (May)\n\n**Key Annual Events & Activities:**\n- Feast of the Conversion of St. Paul (January 25)\n- Paulinian Week / Foundation Day Celebration\n- Intramurals / Sports Festival\n- Academic & Cultural Competitions\n- Community Extension Programs\n- Recognition & Awards Ceremony\n- Commencement Exercises / Graduation\n\nFor the exact dates and detailed schedule of the current academic year, please visit the SPUS Official Website at https://spus.edu.ph or inquire at the Registrar's Office."
    },
    {
        "category": "About PAULA",
        "question": "Who are you? What is PAULA? What does PAULA stand for?",
        "answer": "I am PAULA, which stands for **Paulinian Artificial User Support and Learning Assistant**. I am the official AI campus assistant for Saint Paul University Surigao (SPUS), designed to help students, parents, faculty, and visitors with academic programs, admissions, scholarships, office locations, campus navigation, and university information."
    }
]
