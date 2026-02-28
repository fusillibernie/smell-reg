"""Streamlit-based web interface for smell-reg.

Run with: streamlit run ui/app.py
"""

try:
    import streamlit as st
    import requests
    import pandas as pd
    STREAMLIT_AVAILABLE = True
except ImportError:
    STREAMLIT_AVAILABLE = False
    print("Streamlit is not installed. Run: pip install streamlit")

if STREAMLIT_AVAILABLE:
    import sys
    from pathlib import Path
    from datetime import datetime

    # Add project root to path
    sys.path.insert(0, str(Path(__file__).parent.parent))

    from src.models.regulatory import Market, ProductType
    from src.services.compliance_engine import ComplianceEngine
    from src.services.materials_service import MaterialsService
    from src.services.formula_library import FormulaLibrary
    from src.integrations.aroma_lab import FormulaData, FormulaIngredientData

    # API base URL
    API_BASE = "http://localhost:8000"

    # Compact CSS for spreadsheet-like UI
    CUSTOM_CSS = """
    <style>
        /* Tighter spacing */
        .main .block-container { padding: 1rem 2rem; max-width: 1400px; }

        /* Header */
        h1 { color: #10b981 !important; font-size: 1.8rem !important; margin-bottom: 0 !important; }

        /* Compact inputs */
        .stTextInput > div > div > input,
        .stNumberInput > div > div > input,
        .stSelectbox > div > div {
            padding: 6px 10px !important;
            font-size: 0.9rem !important;
            min-height: 36px !important;
        }

        /* Spreadsheet table styling */
        .spreadsheet-header {
            display: grid;
            grid-template-columns: 120px 1fr 80px 100px 40px;
            gap: 4px;
            padding: 8px 4px;
            background: rgba(16, 185, 129, 0.1);
            border-radius: 6px 6px 0 0;
            font-weight: 600;
            font-size: 0.75rem;
            text-transform: uppercase;
            color: #64748b;
        }
        .spreadsheet-row {
            display: grid;
            grid-template-columns: 120px 1fr 80px 100px 40px;
            gap: 4px;
            padding: 4px;
            border-bottom: 1px solid rgba(255,255,255,0.05);
            align-items: center;
        }
        .spreadsheet-row:hover { background: rgba(255,255,255,0.02); }

        /* Compact status badges */
        .status-ok { color: #10b981; font-size: 0.8rem; }
        .status-warn { color: #f59e0b; font-size: 0.8rem; }
        .status-err { color: #ef4444; font-size: 0.8rem; }

        /* Search results dropdown */
        .search-dropdown {
            background: #1e293b;
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 8px;
            max-height: 300px;
            overflow-y: auto;
        }
        .search-item {
            padding: 10px 12px;
            border-bottom: 1px solid rgba(255,255,255,0.05);
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .search-item:hover { background: rgba(16, 185, 129, 0.1); }

        /* Metrics row */
        .metrics-row {
            display: flex;
            gap: 20px;
            padding: 12px 16px;
            background: rgba(255,255,255,0.03);
            border-radius: 8px;
            margin-top: 12px;
        }
        .metric-item { text-align: center; }
        .metric-value { font-size: 1.4rem; font-weight: 700; color: #10b981; }
        .metric-label { font-size: 0.75rem; color: #64748b; }

        /* Badge styles */
        .badge {
            display: inline-block;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 0.7rem;
            font-weight: 600;
        }
        .badge-allergen { background: rgba(239, 68, 68, 0.2); color: #f87171; }
        .badge-ifra { background: rgba(245, 158, 11, 0.2); color: #fbbf24; }
        .badge-ok { background: rgba(16, 185, 129, 0.2); color: #34d399; }

        /* Hide Streamlit elements */
        #MainMenu, footer, header { visibility: hidden; }
        .stDeployButton { display: none; }

        /* Tab styling */
        .stTabs [data-baseweb="tab-list"] { gap: 4px; }
        .stTabs [data-baseweb="tab"] { padding: 8px 16px; font-size: 0.9rem; }

        /* Buttons */
        .stButton > button { padding: 6px 12px; font-size: 0.85rem; }

        /* Data editor styling */
        [data-testid="stDataEditor"] { font-size: 0.9rem !important; }

        /* Autocomplete container */
        .autocomplete-container {
            position: relative;
            margin-bottom: 16px;
        }
    </style>
    """

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

    @st.cache_data
    def get_all_materials_for_autocomplete():
        """Get all materials formatted for autocomplete dropdown."""
        materials = get_materials_service()
        all_mats = materials.get_all()
        options = []
        for m in all_mats:
            # Format: "Name (CAS)" for display
            label = f"{m.name} ({m.cas_number})"
            options.append({
                "label": label,
                "cas_number": m.cas_number,
                "name": m.name,
                "allergen": m.allergen,
                "ifra_restricted": m.ifra_restricted,
                "volatility": m.volatility,
            })
        return options

    def search_materials(query: str, limit: int = 10) -> list:
        """Search materials database."""
        materials = get_materials_service()
        results = materials.search(query, limit=limit)
        return [m.to_dict() for m in results]

    def autofill_ingredient(cas_or_name: str) -> dict | None:
        """Try to autofill ingredient details from database."""
        if not cas_or_name:
            return None
        materials = get_materials_service()
        material = materials.get_by_cas(cas_or_name)
        if not material:
            material = materials.get_by_name(cas_or_name)
        if material:
            return {
                "cas_number": material.cas_number,
                "name": material.name,
                "inci_name": material.inci_name,
                "allergen": material.allergen,
                "ifra_restricted": material.ifra_restricted,
                "volatility": material.volatility,
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
            st.warning("API server not running. Start with: uvicorn api.main:app")
            return None
        except Exception as e:
            st.error(f"Error: {e}")
            return None

    def get_status_badge(info: dict | None) -> str:
        """Get status badge HTML for an ingredient."""
        if not info:
            return '<span style="color: #64748b;">-</span>'
        badges = []
        if info.get("allergen"):
            badges.append('<span class="badge badge-allergen">A</span>')
        if info.get("ifra_restricted"):
            badges.append('<span class="badge badge-ifra">I</span>')
        if not badges:
            return '<span class="badge badge-ok">OK</span>'
        return " ".join(badges)

    def main():
        st.set_page_config(
            page_title="Smell-Reg",
            page_icon="🧪",
            layout="wide",
            initial_sidebar_state="collapsed",
        )
        st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

        # Header row
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            st.markdown("# Smell-Reg")
        with col2:
            materials = get_materials_service()
            st.caption(f"{materials.get_count()} materials")
        with col3:
            library = get_formula_library()
            st.caption(f"{library.get_count()} formulas")

        # Initialize session state
        if "ingredients" not in st.session_state:
            st.session_state.ingredients = []
        if "formula_name" not in st.session_state:
            st.session_state.formula_name = "New Formula"

        # Sidebar settings
        with st.sidebar:
            st.markdown("### Settings")
            product_type = st.selectbox(
                "Product Type",
                options=[pt.value for pt in ProductType],
                format_func=lambda x: x.replace("_", " ").title(),
            )
            markets = st.multiselect(
                "Markets",
                options=[m.value for m in Market],
                default=["us", "eu"],
                format_func=lambda x: x.upper(),
            )
            fragrance_concentration = st.slider("Fragrance %", 0.1, 100.0, 20.0, 0.1)
            is_leave_on = st.toggle("Leave-on", value=True)

            st.divider()
            if st.button("Load Sample", use_container_width=True):
                st.session_state.ingredients = [
                    {"cas_number": "115-95-7", "name": "Linalyl Acetate", "percentage": 25.0},
                    {"cas_number": "78-70-6", "name": "Linalool", "percentage": 20.0},
                    {"cas_number": "106-22-9", "name": "Citronellol", "percentage": 15.0},
                    {"cas_number": "106-24-1", "name": "Geraniol", "percentage": 10.0},
                    {"cas_number": "101-86-0", "name": "Hexyl Cinnamal", "percentage": 8.0},
                    {"cas_number": "121-33-5", "name": "Vanillin", "percentage": 5.0},
                ]
                st.rerun()

        # Main tabs
        tab1, tab2, tab3, tab4 = st.tabs(["Formula", "Compliance", "Documents", "Library"])

        with tab1:
            # Formula name row
            col1, col2 = st.columns([4, 1])
            with col1:
                formula_name = st.text_input(
                    "Formula Name",
                    value=st.session_state.formula_name,
                    label_visibility="collapsed",
                    placeholder="Formula name...",
                )
                st.session_state.formula_name = formula_name
            with col2:
                if st.button("Save", type="primary", use_container_width=True):
                    if st.session_state.ingredients:
                        library = get_formula_library()
                        library.save(name=formula_name, ingredients=st.session_state.ingredients)
                        st.success("Saved!")
                    else:
                        st.warning("Add ingredients first")

            st.markdown("---")

            # Add ingredient with autocomplete
            st.markdown("**Add Ingredient**")
            all_materials = get_all_materials_for_autocomplete()
            material_options = [""] + [m["label"] for m in all_materials]

            col1, col2, col3 = st.columns([5, 1, 1])
            with col1:
                selected = st.selectbox(
                    "Search material",
                    options=material_options,
                    format_func=lambda x: x if x else "Type to search...",
                    label_visibility="collapsed",
                    key="material_autocomplete",
                )
            with col2:
                add_pct = st.number_input("Pct", value=1.0, min_value=0.1, max_value=100.0, step=0.1, label_visibility="collapsed")
            with col3:
                if st.button("Add", use_container_width=True, disabled=not selected):
                    # Find the selected material
                    for m in all_materials:
                        if m["label"] == selected:
                            # Check for duplicates
                            existing = [i["cas_number"] for i in st.session_state.ingredients]
                            if m["cas_number"] not in existing:
                                st.session_state.ingredients.append({
                                    "cas_number": m["cas_number"],
                                    "name": m["name"],
                                    "percentage": add_pct,
                                })
                                st.rerun()
                            else:
                                st.warning("Already added")
                            break

            st.markdown("---")

            # Ingredients spreadsheet
            if not st.session_state.ingredients:
                st.info("No ingredients. Use the dropdown above to add materials, or load a sample from the sidebar.")
            else:
                # Create DataFrame for editing
                df = pd.DataFrame(st.session_state.ingredients)

                # Display as editable data editor
                edited_df = st.data_editor(
                    df,
                    column_config={
                        "cas_number": st.column_config.TextColumn(
                            "CAS",
                            width="small",
                            help="CAS Registry Number",
                        ),
                        "name": st.column_config.TextColumn(
                            "Name",
                            width="medium",
                        ),
                        "percentage": st.column_config.NumberColumn(
                            "%",
                            width="small",
                            min_value=0.0,
                            max_value=100.0,
                            step=0.1,
                            format="%.2f",
                        ),
                    },
                    hide_index=True,
                    use_container_width=True,
                    num_rows="dynamic",
                    key="ingredient_editor",
                )

                # Update session state from edited dataframe
                st.session_state.ingredients = edited_df.to_dict('records')

                # Status indicators below the table
                st.markdown("**Status:**")
                status_cols = st.columns(min(len(st.session_state.ingredients), 8))
                for i, ing in enumerate(st.session_state.ingredients[:8]):
                    info = autofill_ingredient(ing.get("cas_number", ""))
                    with status_cols[i]:
                        if info:
                            flags = []
                            if info.get("allergen"):
                                flags.append("🔴 A")
                            if info.get("ifra_restricted"):
                                flags.append("🟡 I")
                            if not flags:
                                st.caption(f"✅ {ing.get('name', '')[:8]}")
                            else:
                                st.caption(f"{' '.join(flags)} {ing.get('name', '')[:8]}")
                        else:
                            st.caption(f"⚪ {ing.get('name', '')[:8]}")

            # Summary metrics
            st.markdown("---")
            total_pct = sum(ing.get("percentage", 0) for ing in st.session_state.ingredients)
            allergen_count = sum(1 for ing in st.session_state.ingredients
                                if autofill_ingredient(ing.get("cas_number", "")) and
                                autofill_ingredient(ing.get("cas_number", "")).get("allergen"))
            ifra_count = sum(1 for ing in st.session_state.ingredients
                            if autofill_ingredient(ing.get("cas_number", "")) and
                            autofill_ingredient(ing.get("cas_number", "")).get("ifra_restricted"))

            col1, col2, col3, col4, col5 = st.columns(5)
            with col1:
                st.metric("Total", f"{total_pct:.1f}%")
            with col2:
                st.metric("Count", len(st.session_state.ingredients))
            with col3:
                st.metric("Allergens", allergen_count)
            with col4:
                st.metric("IFRA", ifra_count)
            with col5:
                if abs(total_pct - 100.0) <= 0.5:
                    st.success("Complete")
                elif total_pct > 100:
                    st.error(f"+{total_pct - 100:.1f}%")
                else:
                    st.warning(f"-{100 - total_pct:.1f}%")

            # Action buttons
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("Clear All", use_container_width=True):
                    st.session_state.ingredients = []
                    st.rerun()
            with col2:
                if st.button("Normalize to 100%", use_container_width=True, disabled=total_pct == 0):
                    if total_pct > 0:
                        factor = 100.0 / total_pct
                        for ing in st.session_state.ingredients:
                            ing["percentage"] = round(ing["percentage"] * factor, 2)
                        st.rerun()
            with col3:
                # Export CSV
                if st.session_state.ingredients:
                    csv = "CAS,Name,Percentage\n"
                    for ing in st.session_state.ingredients:
                        csv += f'"{ing.get("cas_number", "")}","{ing.get("name", "")}",{ing.get("percentage", 0)}\n'
                    st.download_button("Export CSV", csv, f"{formula_name}.csv", "text/csv", use_container_width=True)

        with tab2:
            st.markdown("### Compliance Check")

            if not st.session_state.ingredients:
                st.info("Add ingredients in the Formula tab first")
            else:
                if st.button("Run Compliance Check", type="primary", use_container_width=True):
                    engine = get_engine()
                    formula = FormulaData(
                        name=formula_name,
                        ingredients=[
                            FormulaIngredientData(**ing)
                            for ing in st.session_state.ingredients
                            if ing.get("cas_number") and ing.get("percentage", 0) > 0
                        ],
                    )

                    with st.spinner("Checking..."):
                        report = engine.check_compliance(
                            formula=formula,
                            product_type=ProductType(product_type),
                            markets=[Market(m) for m in markets],
                            fragrance_concentration=fragrance_concentration,
                            is_leave_on=is_leave_on,
                        )

                    # Results
                    if report.is_compliant:
                        st.success(f"✅ COMPLIANT - Certificate: {report.certificate_number}")
                    else:
                        st.error(f"❌ NON-COMPLIANT - {len(report.non_compliant_items)} violations")

                    # Violations
                    if report.non_compliant_items:
                        st.markdown("#### Violations")
                        for v in report.non_compliant_items:
                            st.error(f"**{v.requirement}**: {v.details}")

                    # Warnings
                    if report.warnings:
                        st.markdown("#### Warnings")
                        for w in report.warnings:
                            st.warning(f"**{w.requirement}**: {w.details}")

                    # All results
                    with st.expander("All Results"):
                        results_df = pd.DataFrame([
                            {
                                "Requirement": r.requirement,
                                "Status": r.status.value.upper(),
                                "Market": r.market.value.upper(),
                                "Ingredient": r.ingredient_name or "-",
                                "Details": r.details or "-",
                            }
                            for r in report.results
                        ])
                        st.dataframe(results_df, use_container_width=True, hide_index=True)

        with tab3:
            st.markdown("### Generate Documents")

            if not st.session_state.ingredients:
                st.info("Add ingredients first")
            else:
                formula_data = {
                    "name": formula_name,
                    "ingredients": [
                        {"cas_number": ing["cas_number"], "name": ing["name"], "percentage": ing["percentage"]}
                        for ing in st.session_state.ingredients
                        if ing.get("cas_number") and ing.get("percentage", 0) > 0
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
                    st.markdown("**IFRA Certificate**")
                    sig_name = st.text_input("Signatory", value="Quality Manager", key="sig1")
                    sig_title = st.text_input("Title", value="QA Manager", key="sig2")
                    if st.button("Generate IFRA Certificate", use_container_width=True):
                        with st.spinner("Generating..."):
                            pdf = generate_pdf_document("ifra-certificate", formula_data,
                                {**common_settings, "signatory_name": sig_name, "signatory_title": sig_title})
                            if pdf:
                                st.download_button("Download IFRA", pdf,
                                    f"IFRA_{formula_name}_{datetime.now().strftime('%Y%m%d')}.pdf",
                                    "application/pdf", use_container_width=True)

                with col2:
                    st.markdown("**Allergen Statement**")
                    st.write("")
                    st.write("")
                    if st.button("Generate Allergen Statement", use_container_width=True):
                        with st.spinner("Generating..."):
                            pdf = generate_pdf_document("allergen-statement", formula_data, common_settings)
                            if pdf:
                                st.download_button("Download Allergen", pdf,
                                    f"Allergen_{formula_name}_{datetime.now().strftime('%Y%m%d')}.pdf",
                                    "application/pdf", use_container_width=True)

                st.markdown("---")

                col3, col4 = st.columns(2)
                with col3:
                    st.markdown("**VOC Statement**")
                    if st.button("Generate VOC Statement", use_container_width=True):
                        with st.spinner("Generating..."):
                            pdf = generate_pdf_document("voc-statement", formula_data, common_settings)
                            if pdf:
                                st.download_button("Download VOC", pdf,
                                    f"VOC_{formula_name}_{datetime.now().strftime('%Y%m%d')}.pdf",
                                    "application/pdf", use_container_width=True)

                with col4:
                    st.markdown("**FSE Report**")
                    assessor = st.text_input("Assessor", key="assessor")
                    if st.button("Generate FSE", use_container_width=True):
                        with st.spinner("Generating..."):
                            pdf = generate_pdf_document("fse", formula_data,
                                {**common_settings, "assessor": assessor})
                            if pdf:
                                st.download_button("Download FSE", pdf,
                                    f"FSE_{formula_name}_{datetime.now().strftime('%Y%m%d')}.pdf",
                                    "application/pdf", use_container_width=True)

        with tab4:
            st.markdown("### Formula Library")

            library = get_formula_library()
            formulas = library.list_all()

            search = st.text_input("Search formulas...", key="lib_search", label_visibility="collapsed", placeholder="Search...")
            if search:
                formulas = library.search(search)

            if not formulas:
                st.info("No saved formulas")
            else:
                for f in formulas:
                    with st.expander(f"{f.name} ({len(f.ingredients)} ingredients)"):
                        # Show ingredients as table
                        if f.ingredients:
                            ing_df = pd.DataFrame(f.ingredients)
                            st.dataframe(ing_df, use_container_width=True, hide_index=True)

                        col1, col2, col3 = st.columns(3)
                        with col1:
                            if st.button("Load", key=f"load_{f.id}", use_container_width=True):
                                st.session_state.ingredients = f.ingredients.copy()
                                st.session_state.formula_name = f.name
                                st.success(f"Loaded: {f.name}")
                                st.rerun()
                        with col2:
                            if st.button("Duplicate", key=f"dup_{f.id}", use_container_width=True):
                                library.duplicate(f.id)
                                st.rerun()
                        with col3:
                            if st.button("Delete", key=f"del_{f.id}", use_container_width=True):
                                library.delete(f.id)
                                st.rerun()

    if __name__ == "__main__":
        main()
