"""Streamlit-based web interface for smell-reg.

Run with: streamlit run ui/app.py
"""

try:
    import streamlit as st
    STREAMLIT_AVAILABLE = True
except ImportError:
    STREAMLIT_AVAILABLE = False
    print("Streamlit is not installed. Run: pip install streamlit")

if STREAMLIT_AVAILABLE:
    import sys
    from pathlib import Path

    # Add project root to path
    sys.path.insert(0, str(Path(__file__).parent.parent))

    from src.models.regulatory import Market, ProductType
    from src.services.compliance_engine import ComplianceEngine
    from src.integrations.aroma_lab import FormulaData, FormulaIngredientData

    # Initialize services
    @st.cache_resource
    def get_engine():
        return ComplianceEngine()

    def main():
        st.set_page_config(
            page_title="Smell-Reg: Fragrance Compliance",
            page_icon="🧪",
            layout="wide",
        )

        st.title("🧪 Smell-Reg")
        st.subheader("Fragrance Regulatory Compliance Application")

        # Sidebar for settings
        with st.sidebar:
            st.header("Settings")

            product_type = st.selectbox(
                "Product Type",
                options=[pt.value for pt in ProductType],
                format_func=lambda x: x.replace("_", " ").title(),
            )

            markets = st.multiselect(
                "Target Markets",
                options=[m.value for m in Market],
                default=["us", "eu"],
                format_func=lambda x: x.upper(),
            )

            fragrance_concentration = st.slider(
                "Fragrance Concentration (%)",
                min_value=0.1,
                max_value=100.0,
                value=20.0,
                step=0.1,
            )

            is_leave_on = st.checkbox("Leave-on Product", value=True)

        # Main content
        tab1, tab2, tab3, tab4 = st.tabs([
            "📝 Formula Input",
            "✅ Compliance Check",
            "📄 Documents",
            "📊 Reports",
        ])

        with tab1:
            st.header("Formula Input")

            formula_name = st.text_input("Formula Name", value="My Fragrance")

            st.subheader("Ingredients")

            # Initialize session state for ingredients
            if "ingredients" not in st.session_state:
                st.session_state.ingredients = [
                    {"cas_number": "64-17-5", "name": "Ethanol", "percentage": 70.0},
                    {"cas_number": "78-70-6", "name": "Linalool", "percentage": 10.0},
                ]

            # Ingredient editor
            for i, ing in enumerate(st.session_state.ingredients):
                col1, col2, col3, col4 = st.columns([2, 3, 2, 1])
                with col1:
                    st.session_state.ingredients[i]["cas_number"] = st.text_input(
                        "CAS", value=ing["cas_number"], key=f"cas_{i}"
                    )
                with col2:
                    st.session_state.ingredients[i]["name"] = st.text_input(
                        "Name", value=ing["name"], key=f"name_{i}"
                    )
                with col3:
                    st.session_state.ingredients[i]["percentage"] = st.number_input(
                        "%", value=ing["percentage"], min_value=0.0, max_value=100.0,
                        key=f"pct_{i}"
                    )
                with col4:
                    if st.button("🗑️", key=f"del_{i}"):
                        st.session_state.ingredients.pop(i)
                        st.rerun()

            if st.button("➕ Add Ingredient"):
                st.session_state.ingredients.append({
                    "cas_number": "",
                    "name": "",
                    "percentage": 0.0,
                })
                st.rerun()

            # Total percentage
            total_pct = sum(ing["percentage"] for ing in st.session_state.ingredients)
            st.metric("Total Percentage", f"{total_pct:.2f}%")
            if abs(total_pct - 100.0) > 0.1:
                st.warning("Total percentage should equal 100%")

        with tab2:
            st.header("Compliance Check")

            if st.button("Run Compliance Check", type="primary"):
                engine = get_engine()

                # Build formula
                formula = FormulaData(
                    name=formula_name,
                    ingredients=[
                        FormulaIngredientData(**ing)
                        for ing in st.session_state.ingredients
                        if ing["cas_number"] and ing["percentage"] > 0
                    ],
                )

                # Run check
                with st.spinner("Checking compliance..."):
                    report = engine.check_compliance(
                        formula=formula,
                        product_type=ProductType(product_type),
                        markets=[Market(m) for m in markets],
                        fragrance_concentration=fragrance_concentration,
                        is_leave_on=is_leave_on,
                    )

                # Display results
                st.subheader("Results")

                if report.is_compliant:
                    st.success(f"✅ Formula is COMPLIANT")
                    if report.certificate_number:
                        st.info(f"Certificate Number: {report.certificate_number}")
                else:
                    st.error("❌ Formula is NON-COMPLIANT")

                # Show violations
                if report.non_compliant_items:
                    st.subheader("Violations")
                    for v in report.non_compliant_items:
                        st.error(f"**{v.requirement}**: {v.details}")

                # Show warnings
                if report.warnings:
                    st.subheader("Warnings")
                    for w in report.warnings:
                        st.warning(f"**{w.requirement}**: {w.details}")

                # Show all results in table
                st.subheader("All Results")
                results_data = [
                    {
                        "Requirement": r.requirement,
                        "Status": r.status.value,
                        "Market": r.market.value.upper(),
                        "Ingredient": r.ingredient_name or "-",
                        "Details": r.details or "-",
                    }
                    for r in report.results
                ]
                st.dataframe(results_data)

        with tab3:
            st.header("Document Generation")

            col1, col2 = st.columns(2)

            with col1:
                st.subheader("IFRA Certificate")
                signatory_name = st.text_input("Signatory Name", value="Quality Manager")
                signatory_title = st.text_input("Signatory Title", value="Quality Assurance")
                if st.button("Generate IFRA Certificate"):
                    st.info("PDF generation requires WeasyPrint. Check API endpoint for PDF generation.")

            with col2:
                st.subheader("Allergen Statement")
                if st.button("Generate Allergen Statement"):
                    st.info("PDF generation requires WeasyPrint. Check API endpoint for PDF generation.")

            col3, col4 = st.columns(2)

            with col3:
                st.subheader("VOC Statement")
                if st.button("Generate VOC Statement"):
                    st.info("PDF generation requires WeasyPrint. Check API endpoint for PDF generation.")

            with col4:
                st.subheader("FSE Report")
                assessor = st.text_input("Assessor Name", value="")
                intended_use = st.text_area("Intended Use", value="")
                if st.button("Generate FSE"):
                    st.info("PDF generation requires WeasyPrint. Check API endpoint for PDF generation.")

        with tab4:
            st.header("Compliance Reports")

            st.subheader("Quick Checks")

            check_type = st.selectbox(
                "Select Check Type",
                options=["IFRA Only", "Allergens Only", "VOC Only", "FSE Generation"],
            )

            if st.button("Run Quick Check"):
                engine = get_engine()

                formula = FormulaData(
                    name=formula_name,
                    ingredients=[
                        FormulaIngredientData(**ing)
                        for ing in st.session_state.ingredients
                        if ing["cas_number"] and ing["percentage"] > 0
                    ],
                )

                with st.spinner("Running check..."):
                    if check_type == "IFRA Only":
                        result = engine.check_ifra(
                            formula=formula,
                            product_type=ProductType(product_type),
                            fragrance_concentration=fragrance_concentration,
                        )
                        st.json({
                            "is_compliant": result.is_compliant,
                            "violations": [v.to_dict() for v in result.violations],
                            "warnings": [w.to_dict() for w in result.warnings],
                        })

                    elif check_type == "Allergens Only":
                        report = engine.check_allergens(
                            formula=formula,
                            markets=[Market(m) for m in markets],
                            fragrance_concentration=fragrance_concentration,
                            is_leave_on=is_leave_on,
                        )
                        st.json(report.to_dict())

                    elif check_type == "VOC Only":
                        report = engine.check_voc(
                            formula=formula,
                            product_type=ProductType(product_type),
                            markets=[Market(m) for m in markets],
                        )
                        st.json(report.to_dict())

                    elif check_type == "FSE Generation":
                        report = engine.generate_fse(
                            formula=formula,
                            product_type=ProductType(product_type),
                            fragrance_concentration=fragrance_concentration,
                        )
                        st.json(report.to_dict())

    if __name__ == "__main__":
        main()
