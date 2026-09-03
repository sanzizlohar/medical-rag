"""Generate a small sample medical PDF for testing the RAG pipeline."""

import fitz

PAGES = [
    # Page 1: Dengue
    """Dengue Fever — Fact Sheet

Overview
Dengue fever is a viral infection transmitted to humans through the bite of infected
Aedes mosquitoes, primarily Aedes aegypti. It is common in tropical and subtropical
regions including Southeast Asia, Latin America, and Africa.

Common Symptoms
Symptoms usually begin 4 to 10 days after infection and last 2 to 7 days. They include:
- High fever (40 C / 104 F)
- Severe headache, often behind the eyes
- Muscle, bone, and joint pain (historically called break-bone fever)
- Nausea and vomiting
- Swollen glands
- Skin rash appearing 2 to 5 days after the onset of fever

Warning Signs of Severe Dengue
Severe dengue (dengue hemorrhagic fever) usually appears after the fever has subsided.
Warning signs include severe abdominal pain, persistent vomiting, rapid breathing,
bleeding gums or nose, fatigue, restlessness, and blood in vomit or stool. Severe
dengue is a medical emergency and requires immediate hospital care.

Treatment
There is no specific antiviral treatment for dengue. Patients should rest, drink
plenty of fluids, and use paracetamol (acetaminophen) for fever and pain relief.
Aspirin and ibuprofen should be avoided because they increase the risk of bleeding.
""",

    # Page 2: Hypertension
    """High Blood Pressure (Hypertension) — Fact Sheet

Definition
Hypertension is diagnosed when blood pressure readings are consistently 140/90 mmHg
or higher. Normal blood pressure is around 120/80 mmHg. Uncontrolled hypertension
increases the risk of heart disease, stroke, and kidney failure.

Risk Factors
Modifiable risk factors include a diet high in salt, physical inactivity, obesity,
tobacco use, and excessive alcohol consumption. Non-modifiable factors include age,
family history, and chronic conditions such as diabetes.

Lifestyle Management
Recommended lifestyle changes include reducing dietary sodium to less than 2 grams
per day, engaging in at least 150 minutes of moderate aerobic exercise per week,
maintaining a healthy body weight, limiting alcohol, and stopping tobacco use.

Medication
Common first-line antihypertensive drug classes include thiazide diuretics,
ACE inhibitors, angiotensin II receptor blockers (ARBs), and calcium channel
blockers. Treatment choice depends on the individual patient profile and should
be made by a qualified physician.
""",

    # Page 3: Type 2 Diabetes
    """Type 2 Diabetes — Fact Sheet

Overview
Type 2 diabetes is a chronic metabolic condition in which the body becomes resistant
to insulin or does not produce enough insulin, leading to elevated blood glucose.
It accounts for more than 90 percent of all diabetes cases.

Diagnostic Criteria
A fasting plasma glucose of 126 mg/dL (7.0 mmol/L) or higher, an HbA1c of 6.5 percent
or higher, or a 2-hour plasma glucose of 200 mg/dL (11.1 mmol/L) during an oral
glucose tolerance test indicates diabetes.

Symptoms
Common symptoms include increased thirst, frequent urination, unexplained weight
loss, fatigue, blurred vision, and slow-healing wounds. Many people have no symptoms
in the early stages.

Management
First-line management includes metformin combined with lifestyle modification.
Newer drug classes such as GLP-1 receptor agonists and SGLT2 inhibitors offer
additional cardiovascular and renal benefits. Regular screening for retinopathy,
nephropathy, and neuropathy is recommended for all patients.
""",
]


def main():
    doc = fitz.open()
    for page_text in PAGES:
        page = doc.new_page()
        rect = fitz.Rect(50, 50, 545, 792)
        page.insert_textbox(rect, page_text, fontsize=11, fontname="helv")
    out = "sample_data/medical_fact_sheets.pdf"
    doc.save(out)
    doc.close()
    print(f"Created {out} with {len(PAGES)} pages")


if __name__ == "__main__":
    main()
