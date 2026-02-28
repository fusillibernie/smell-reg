"""Streamlit-based web interface for smell-reg.

Run with: streamlit run ui/app.py
"""

try:
    import streamlit as st
    import requests
    STREAMLIT_AVAILABLE = True
except ImportError:
    STREAMLIT_AVAILABLE = False
    print("Streamlit is not installed. Run: pip install streamlit")

if STREAMLIT_AVAILABLE:
    import sys
    import base64
    from pathlib import Path
    from io import BytesIO

    # Add project root to path
    sys.path.insert(0, str(Path(__file__).parent.parent))

    from src.models.regulatory import Market, ProductType
    from src.services.compliance_engine import ComplianceEngine
    from src.services.materials_service import MaterialsService
    from src.services.formula_library import FormulaLibrary
    from src.integrations.aroma_lab import FormulaData, FormulaIngredientData

    # API base URL
    API_BASE = "http://localhost:8000"

    # Initialize services
    @st.cache_resource
    def get_engine():
        return ComplianceEngine()

    @st.cache_resource
    def get_materials_service():
        return MaterialsService()

    @st.cache_resource
    def get_formula_library():
        return FormulaLibrary()

    def search_materials(query: str, limit: int = 10) -> list:
        """Search materials database."""
        materials = get_materials_service()
        results = materials.search(query, limit=limit)
        return [m.to_dict() for m in results]

    def autofill_ingredient(cas_or_name: str) -> dict | None:
        """Try to autofill ingredient details from database."""
        materials = get_materials_service()

        # Try CAS first
        material = materials.get_by_cas(cas_or_name)
        if not material:
            # Try name
            material = materials.get_by_name(cas_or_name)

        if material:
            return {
                "cas_number": material.cas_number,
                "name": material.name,
                "inci_name": material.inci_name,
                "allergen": material.allergen,
                "ifra_restricted": material.ifra_restricted,
            }
        return None

    def generate_pdf_document(doc_type: str, formula_data: dict, settings: dict) -> bytes | None:
        """Generate PDF document via API."""
        try:
            endpoint = f"{API_BASE}/api/documents/{doc_type}"
            response = requests.post(endpoint, json={
                "formula": formula_data,
                **settings,
            }, timeout=30)

            if response.status_code == 200:
                return response.content
            else:
                st.error(f"Error generating PDF: {response.text}")
                return None
        except requests.exceptions.ConnectionError:
            st.warning("API server not running. Starting local generation...")
            return None
        except Exception as e:
            st.error(f"Error: {e}")
            return None

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

            st.divider()

            # Materials database stats
            materials = get_materials_service()
            st.caption(f"📦 {materials.get_count()} materials in database")

            library = get_formula_library()
            st.caption(f"📚 {library.get_count()} formulas in library")

        # Main content
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "📝 Formula Input",
            "✅ Compliance Check",
            "📄 Documents",
            "📚 Formula Library",
            "📊 Reports",
        ])

        with tab1:
            st.header("Formula Input")

            col1, col2 = st.columns([3, 1])
            with col1:
                formula_name = st.text_input("Formula Name", value="My Fragrance")
            with col2:
                if st.button("💾 Save to Library"):
                    if st.session_state.get("ingredients"):
                        library = get_formula_library()
                        library.save(
                            name=formula_name,
                            ingredients=st.session_state.ingredients,
                        )
                        st.success("Formula saved to library!")
                    else:
                        st.warning("Add ingredients first")

            st.subheader("Ingredient Search")
            search_query = st.text_input(
                "🔍 Search materials (name, CAS, or INCI)",
                placeholder="Type to search...",
                key="material_search",
            )

            if search_query and len(search_query) >= 2:
                results = search_materials(search_query)
                if results:
                    st.caption(f"Found {len(results)} materials")
                    for mat in results[:5]:
                        col1, col2, col3 = st.columns([3, 1, 1])
                        with col1:
                            allergen_badge = "⚠️" if mat.get("allergen") else ""
                            ifra_badge = "🔒" if mat.get("ifra_restricted") else ""
                            st.write(f"**{mat['name']}** {allergen_badge}{ifra_badge}")
                            st.caption(f"CAS: {mat['cas_number']} | INCI: {mat['inci_name']}")
                        with col2:
                            st.caption(mat.get("volatility", "").title())
                        with col3:
                            if st.button("Add", key=f"add_{mat['cas_number']}"):
                                if "ingredients" not in st.session_state:
                                    st.session_state.ingredients = []
                                st.session_state.ingredients.append({
                                    "cas_number": mat["cas_number"],
                                    "name": mat["name"],
                                    "percentage": 1.0,
                                })
                                st.rerun()
                else:
                    st.info("No materials found. Try a different search term.")

            st.divider()
            st.subheader("Ingredients")

            # Initialize session state for ingredients
            if "ingredients" not in st.session_state:
                st.session_state.ingredients = []

            # Ingredient editor
            for i, ing in enumerate(st.session_state.ingredients):
                col1, col2, col3, col4, col5 = st.columns([2, 3, 1.5, 1, 0.5])
                with col1:
                    new_cas = st.text_input(
                        "CAS", value=ing["cas_number"], key=f"cas_{i}",
                        label_visibility="collapsed" if i > 0 else "visible",
                    )
                    # Auto-fill on CAS change
                    if new_cas != ing["cas_number"]:
                        autofill = autofill_ingredient(new_cas)
                        if autofill:
                            st.session_state.ingredients[i]["cas_number"] = autofill["cas_number"]
                            st.session_state.ingredients[i]["name"] = autofill["name"]
                            st.rerun()
                        else:
                            st.session_state.ingredients[i]["cas_number"] = new_cas

                with col2:
                    new_name = st.text_input(
                        "Name", value=ing["name"], key=f"name_{i}",
                        label_visibility="collapsed" if i > 0 else "visible",
                    )
                    # Auto-fill on name change
                    if new_name != ing["name"]:
                        autofill = autofill_ingredient(new_name)
                        if autofill:
                            st.session_state.ingredients[i]["cas_number"] = autofill["cas_number"]
                            st.session_state.ingredients[i]["name"] = autofill["name"]
                            st.rerun()
                        else:
                            st.session_state.ingredients[i]["name"] = new_name

                with col3:
                    st.session_state.ingredients[i]["percentage"] = st.number_input(
                        "%", value=ing["percentage"], min_value=0.0, max_value=100.0,
                        key=f"pct_{i}",
                        label_visibility="collapsed" if i > 0 else "visible",
                    )
                with col4:
                    # Show allergen/IFRA status
                    info = autofill_ingredient(ing["cas_number"])
                    if info:
                        badges = []
                        if info.get("allergen"):
                            badges.append("⚠️")
                        if info.get("ifra_restricted"):
                            badges.append("🔒")
                        st.write(" ".join(badges) if badges else "✓")
                    else:
                        st.write("")
                with col5:
                    if st.button("🗑️", key=f"del_{i}"):
                        st.session_state.ingredients.pop(i)
                        st.rerun()

            col1, col2 = st.columns([1, 4])
            with col1:
                if st.button("➕ Add Ingredient"):
                    st.session_state.ingredients.append({
                        "cas_number": "",
                        "name": "",
                        "percentage": 0.0,
                    })
                    st.rerun()
            with col2:
                if st.button("🧹 Clear All"):
                    st.session_state.ingredients = []
                    st.rerun()

            # Total percentage
            total_pct = sum(ing["percentage"] for ing in st.session_state.ingredients)
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Total Percentage", f"{total_pct:.2f}%")
            with col2:
                st.metric("Ingredient Count", len(st.session_state.ingredients))

            if abs(total_pct - 100.0) > 0.1:
                st.warning("Total percentage should equal 100%")

        with tab2:
            st.header("Compliance Check")

            if st.button("Run Compliance Check", type="primary"):
                if not st.session_state.get("ingredients"):
                    st.warning("Add ingredients first in the Formula Input tab")
                else:
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
                        st.success("✅ Formula is COMPLIANT")
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

            if not st.session_state.get("ingredients"):
                st.info("Add ingredients in the Formula Input tab first")
            else:
                formula_data = {
                    "name": formula_name,
                    "ingredients": [
                        {
                            "cas_number": ing["cas_number"],
                            "name": ing["name"],
                            "percentage": ing["percentage"],
                        }
                        for ing in st.session_state.ingredients
                        if ing["cas_number"] and ing["percentage"] > 0
                    ],
                }

                common_settings = {
                    "product_type": product_type,
                    "markets": markets,
                    "fragrance_concentration": fragrance_concentration,
                    "is_leave_on": is_leave_on,
                }

                col1, col2 = st.columns(2)

                with col1:
                    st.subheader("IFRA Certificate")
                    signatory_name = st.text_input("Signatory Name", value="Quality Manager")
                    signatory_title = st.text_input("Signatory Title", value="Quality Assurance")

                    if st.button("📄 Generate IFRA Certificate", type="primary"):
                        with st.spinner("Generating PDF..."):
                            pdf_bytes = generate_pdf_document(
                                "ifra-certificate",
                                formula_data,
                                {**common_settings, "signatory_name": signatory_name, "signatory_title": signatory_title},
                            )
                            if pdf_bytes:
                                st.download_button(
                                    "⬇️ Download IFRA Certificate",
                                    data=pdf_bytes,
                                    file_name=f"IFRA_Certificate_{formula_name}.pdf",
                                    mime="application/pdf",
                                )

                with col2:
                    st.subheader("Allergen Statement")
                    if st.button("📄 Generate Allergen Statement", type="primary"):
                        with st.spinner("Generating PDF..."):
                            pdf_bytes = generate_pdf_document(
                                "allergen-statement",
                                formula_data,
                                common_settings,
                            )
                            if pdf_bytes:
                                st.download_button(
                                    "⬇️ Download Allergen Statement",
                                    data=pdf_bytes,
                                    file_name=f"Allergen_Statement_{formula_name}.pdf",
                                    mime="application/pdf",
                                )

                col3, col4 = st.columns(2)

                with col3:
                    st.subheader("VOC Statement")
                    if st.button("📄 Generate VOC Statement", type="primary"):
                        with st.spinner("Generating PDF..."):
                            pdf_bytes = generate_pdf_document(
                                "voc-statement",
                                formula_data,
                                common_settings,
                            )
                            if pdf_bytes:
                                st.download_button(
                                    "⬇️ Download VOC Statement",
                                    data=pdf_bytes,
                                    file_name=f"VOC_Statement_{formula_name}.pdf",
                                    mime="application/pdf",
                                )

                with col4:
                    st.subheader("FSE Report")
                    assessor = st.text_input("Assessor Name", value="")
                    intended_use = st.text_area("Intended Use", value="")

                    if st.button("📄 Generate FSE", type="primary"):
                        with st.spinner("Generating PDF..."):
                            pdf_bytes = generate_pdf_document(
                                "fse",
                                formula_data,
                                {**common_settings, "assessor": assessor, "intended_use": intended_use},
                            )
                            if pdf_bytes:
                                st.download_button(
                                    "⬇️ Download FSE Report",
                                    data=pdf_bytes,
                                    file_name=f"FSE_{formula_name}.pdf",
                                    mime="application/pdf",
                                )

        with tab4:
            st.header("Formula Library")

            library = get_formula_library()
            formulas = library.list_all()

            if not formulas:
                st.info("No formulas saved yet. Save a formula from the Formula Input tab.")
            else:
                # Search
                search = st.text_input("🔍 Search formulas", placeholder="Search by name or tags...")
                if search:
                    formulas = library.search(search)

                st.caption(f"Showing {len(formulas)} formula(s)")

                for formula in formulas:
                    with st.expander(f"📋 {formula.name}", expanded=False):
                        col1, col2, col3 = st.columns([2, 1, 1])

                        with col1:
                            st.caption(f"ID: {formula.id[:8]}...")
                            if formula.description:
                                st.write(formula.description)
                            if formula.tags:
                                st.write("Tags: " + ", ".join(formula.tags))

                        with col2:
                            st.metric("Ingredients", len(formula.ingredients))
                            if formula.compliance_status:
                                if formula.compliance_status == "compliant":
                                    st.success("✅ Compliant")
                                else:
                                    st.error("❌ Non-compliant")

                        with col3:
                            st.caption(f"Updated: {formula.updated_at[:10]}")

                        # Ingredient table
                        st.write("**Ingredients:**")
                        ing_data = [
                            {
                                "CAS": ing["cas_number"],
                                "Name": ing["name"],
                                "%": ing["percentage"],
                            }
                            for ing in formula.ingredients
                        ]
                        st.dataframe(ing_data, use_container_width=True)

                        # Actions
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            if st.button("📥 Load", key=f"load_{formula.id}"):
                                st.session_state.ingredients = formula.ingredients.copy()
                                st.success(f"Loaded {formula.name}")
                                st.rerun()
                        with col2:
                            if st.button("📋 Duplicate", key=f"dup_{formula.id}"):
                                library.duplicate(formula.id)
                                st.success("Formula duplicated")
                                st.rerun()
                        with col3:
                            if st.button("🗑️ Delete", key=f"del_lib_{formula.id}"):
                                library.delete(formula.id)
                                st.success("Formula deleted")
                                st.rerun()

        with tab5:
            st.header("Compliance Reports")

            st.subheader("Quick Checks")

            check_type = st.selectbox(
                "Select Check Type",
                options=["IFRA Only", "Allergens Only", "VOC Only", "FSE Generation"],
            )

            if st.button("Run Quick Check"):
                if not st.session_state.get("ingredients"):
                    st.warning("Add ingredients first")
                else:
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
