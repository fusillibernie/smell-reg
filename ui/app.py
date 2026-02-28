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

    # Custom CSS for modern look
    CUSTOM_CSS = """
    <style>
        /* Root variables */
        :root {
            --primary: #10b981;
            --primary-dark: #059669;
            --primary-light: #34d399;
            --danger: #ef4444;
            --warning: #f59e0b;
            --info: #3b82f6;
            --success: #10b981;
        }

        /* Main container */
        .main .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
            max-width: 1200px;
        }

        /* Header styling */
        h1 {
            color: #10b981 !important;
            font-weight: 700 !important;
            letter-spacing: -0.5px;
        }

        /* Card styling */
        .stExpander {
            background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
            border: 1px solid rgba(255,255,255,0.1) !important;
            border-radius: 12px !important;
        }

        /* Button styling */
        .stButton > button {
            border-radius: 8px;
            font-weight: 600;
            transition: all 0.2s;
        }
        .stButton > button:hover {
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.2);
        }
        .stButton > button[kind="primary"] {
            background: linear-gradient(135deg, #10b981 0%, #059669 100%);
        }

        /* Input styling */
        .stTextInput > div > div > input,
        .stSelectbox > div > div > select,
        .stNumberInput > div > div > input {
            border-radius: 8px !important;
            border: 1px solid rgba(255,255,255,0.2) !important;
        }
        .stTextInput > div > div > input:focus,
        .stSelectbox > div > div > select:focus {
            border-color: #10b981 !important;
            box-shadow: 0 0 0 2px rgba(16,185,129,0.2) !important;
        }

        /* Tab styling */
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
        }
        .stTabs [data-baseweb="tab"] {
            border-radius: 8px 8px 0 0;
            padding: 12px 20px;
            font-weight: 600;
        }

        /* Metric styling */
        [data-testid="stMetricValue"] {
            font-size: 1.8rem !important;
            color: #10b981 !important;
        }

        /* Badge styles */
        .badge {
            display: inline-block;
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 0.75rem;
            font-weight: 600;
            margin: 2px;
        }
        .badge-allergen {
            background: rgba(239, 68, 68, 0.2);
            color: #f87171;
            border: 1px solid rgba(239, 68, 68, 0.3);
        }
        .badge-ifra {
            background: rgba(245, 158, 11, 0.2);
            color: #fbbf24;
            border: 1px solid rgba(245, 158, 11, 0.3);
        }
        .badge-compliant {
            background: rgba(16, 185, 129, 0.2);
            color: #34d399;
            border: 1px solid rgba(16, 185, 129, 0.3);
        }
        .badge-warning {
            background: rgba(245, 158, 11, 0.2);
            color: #fbbf24;
        }

        /* Progress step styling */
        .step-container {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
        }
        .step {
            flex: 1;
            padding: 12px;
            text-align: center;
            border-radius: 8px;
            background: rgba(255,255,255,0.05);
            border: 2px solid transparent;
        }
        .step.active {
            border-color: #10b981;
            background: rgba(16, 185, 129, 0.1);
        }
        .step.complete {
            background: rgba(16, 185, 129, 0.15);
            border-color: #10b981;
        }
        .step-num {
            width: 28px;
            height: 28px;
            line-height: 28px;
            background: rgba(255,255,255,0.1);
            border-radius: 50%;
            display: inline-block;
            margin-bottom: 6px;
            font-weight: 600;
        }
        .step.active .step-num, .step.complete .step-num {
            background: #10b981;
            color: #fff;
        }

        /* Material card */
        .material-card {
            background: rgba(255,255,255,0.03);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 10px;
            padding: 14px;
            margin-bottom: 10px;
            transition: all 0.2s;
        }
        .material-card:hover {
            background: rgba(255,255,255,0.06);
            border-color: rgba(16, 185, 129, 0.3);
        }

        /* Ingredient row */
        .ingredient-row {
            background: rgba(255,255,255,0.03);
            border-radius: 8px;
            padding: 10px;
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            gap: 12px;
        }

        /* Empty state */
        .empty-state {
            text-align: center;
            padding: 40px 20px;
            color: #64748b;
        }
        .empty-icon {
            font-size: 3rem;
            margin-bottom: 16px;
            opacity: 0.5;
        }

        /* Info cards */
        .info-card {
            background: linear-gradient(135deg, rgba(16,185,129,0.1) 0%, rgba(16,185,129,0.05) 100%);
            border: 1px solid rgba(16,185,129,0.2);
            border-radius: 12px;
            padding: 16px;
            margin-bottom: 16px;
        }

        /* Compliance result */
        .result-compliant {
            background: linear-gradient(135deg, rgba(16,185,129,0.15) 0%, rgba(16,185,129,0.05) 100%);
            border: 2px solid #10b981;
            border-radius: 12px;
            padding: 20px;
            text-align: center;
        }
        .result-non-compliant {
            background: linear-gradient(135deg, rgba(239,68,68,0.15) 0%, rgba(239,68,68,0.05) 100%);
            border: 2px solid #ef4444;
            border-radius: 12px;
            padding: 20px;
            text-align: center;
        }

        /* Document cards */
        .doc-card {
            background: rgba(255,255,255,0.03);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 12px;
            padding: 20px;
            height: 100%;
        }
        .doc-card h4 {
            color: #10b981;
            margin-bottom: 12px;
        }

        /* Hide streamlit elements */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
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

    def render_progress_steps(current_step: int):
        """Render workflow progress steps."""
        steps = ["Formula Input", "Compliance Check", "Generate Documents"]
        html = '<div class="step-container">'
        for i, step in enumerate(steps):
            status = "complete" if i < current_step else ("active" if i == current_step else "")
            html += f'''
                <div class="step {status}">
                    <div class="step-num">{i + 1}</div>
                    <div>{step}</div>
                </div>
            '''
        html += '</div>'
        st.markdown(html, unsafe_allow_html=True)

    def render_material_badges(info: dict) -> str:
        """Render badges for material properties."""
        badges = []
        if info.get("allergen"):
            badges.append('<span class="badge badge-allergen">Allergen</span>')
        if info.get("ifra_restricted"):
            badges.append('<span class="badge badge-ifra">IFRA Restricted</span>')
        if not badges:
            badges.append('<span class="badge badge-compliant">Clear</span>')
        return " ".join(badges)

    def main():
        st.set_page_config(
            page_title="Smell-Reg: Fragrance Compliance",
            page_icon="&#129514;",
            layout="wide",
            initial_sidebar_state="expanded",
        )

        # Inject custom CSS
        st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

        # Header
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown("# Smell-Reg")
            st.caption("Fragrance Regulatory Compliance Application")
        with col2:
            materials = get_materials_service()
            library = get_formula_library()
            st.markdown(f"""
                <div style="text-align: right; color: #64748b; font-size: 0.85rem;">
                    <strong>{materials.get_count()}</strong> materials |
                    <strong>{library.get_count()}</strong> formulas
                </div>
            """, unsafe_allow_html=True)

        # Sidebar for settings
        with st.sidebar:
            st.markdown("### Settings")

            product_type = st.selectbox(
                "Product Type",
                options=[pt.value for pt in ProductType],
                format_func=lambda x: x.replace("_", " ").title(),
                help="Select the type of product this fragrance will be used in",
            )

            markets = st.multiselect(
                "Target Markets",
                options=[m.value for m in Market],
                default=["us", "eu"],
                format_func=lambda x: x.upper(),
                help="Select all markets where the product will be sold",
            )

            fragrance_concentration = st.slider(
                "Fragrance Concentration (%)",
                min_value=0.1,
                max_value=100.0,
                value=20.0,
                step=0.1,
                help="Percentage of fragrance in the final product",
            )

            is_leave_on = st.toggle("Leave-on Product", value=True, help="Products that remain on skin vs rinse-off")

            st.divider()

            # Quick actions
            st.markdown("### Quick Actions")
            if st.button("Clear Formula", use_container_width=True):
                st.session_state.ingredients = []
                st.rerun()

            if st.button("Sample Formula", use_container_width=True):
                st.session_state.ingredients = [
                    {"cas_number": "115-95-7", "name": "Linalyl Acetate", "percentage": 25.0},
                    {"cas_number": "78-70-6", "name": "Linalool", "percentage": 20.0},
                    {"cas_number": "106-22-9", "name": "Citronellol", "percentage": 15.0},
                    {"cas_number": "106-24-1", "name": "Geraniol", "percentage": 10.0},
                    {"cas_number": "101-86-0", "name": "Hexyl Cinnamal", "percentage": 8.0},
                ]
                st.success("Sample formula loaded!")
                st.rerun()

        # Initialize session state
        if "ingredients" not in st.session_state:
            st.session_state.ingredients = []
        if "formula_name" not in st.session_state:
            st.session_state.formula_name = "My Fragrance"
        if "current_step" not in st.session_state:
            st.session_state.current_step = 0

        # Main content tabs
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "Formula Input",
            "Compliance Check",
            "Documents",
            "Formula Library",
            "Reports",
        ])

        with tab1:
            render_progress_steps(0)

            # Formula name and save
            col1, col2 = st.columns([4, 1])
            with col1:
                formula_name = st.text_input(
                    "Formula Name",
                    value=st.session_state.formula_name,
                    placeholder="Enter a name for your formula...",
                )
                st.session_state.formula_name = formula_name
            with col2:
                st.write("")  # Spacing
                st.write("")
                if st.button("Save to Library", type="primary", use_container_width=True):
                    if st.session_state.get("ingredients"):
                        library = get_formula_library()
                        library.save(
                            name=formula_name,
                            ingredients=st.session_state.ingredients,
                        )
                        st.success("Formula saved!")
                    else:
                        st.warning("Add ingredients first")

            st.divider()

            # Ingredient search
            st.markdown("### Add Ingredients")
            st.caption("Search by name, CAS number, or INCI name")

            search_query = st.text_input(
                "Search materials",
                placeholder="Type to search (e.g., 'linalool', '78-70-6', 'citrus')...",
                key="material_search",
                label_visibility="collapsed",
            )

            if search_query and len(search_query) >= 2:
                results = search_materials(search_query)
                if results:
                    st.caption(f"Found {len(results)} materials")
                    for mat in results[:6]:
                        with st.container():
                            col1, col2, col3 = st.columns([4, 2, 1])
                            with col1:
                                badges_html = render_material_badges(mat)
                                st.markdown(f"""
                                    <div class="material-card">
                                        <strong style="color: #f0f0f0;">{mat['name']}</strong> {badges_html}
                                        <div style="font-size: 0.85rem; color: #64748b; margin-top: 4px;">
                                            CAS: {mat['cas_number']} | INCI: {mat.get('inci_name', '-')}
                                        </div>
                                    </div>
                                """, unsafe_allow_html=True)
                            with col2:
                                vol = mat.get("volatility", "heart")
                                vol_colors = {"top": "#ef4444", "heart": "#10b981", "base": "#8b5cf6"}
                                st.markdown(f"""
                                    <div style="text-align: center; padding: 10px;">
                                        <span style="color: {vol_colors.get(vol, '#888')}; font-weight: 600;">
                                            {vol.upper() if vol else 'HEART'}
                                        </span>
                                    </div>
                                """, unsafe_allow_html=True)
                            with col3:
                                if st.button("Add", key=f"add_{mat['cas_number']}", use_container_width=True):
                                    # Check for duplicates
                                    existing_cas = [i["cas_number"] for i in st.session_state.ingredients]
                                    if mat["cas_number"] in existing_cas:
                                        st.warning("Already added!")
                                    else:
                                        st.session_state.ingredients.append({
                                            "cas_number": mat["cas_number"],
                                            "name": mat["name"],
                                            "percentage": 1.0,
                                        })
                                        st.rerun()
                else:
                    st.info("No materials found. Try a different search term.")

            st.divider()

            # Current ingredients
            st.markdown("### Formula Ingredients")

            if not st.session_state.ingredients:
                st.markdown("""
                    <div class="empty-state">
                        <div class="empty-icon">&#128218;</div>
                        <div><strong>No ingredients yet</strong></div>
                        <div style="font-size: 0.9rem;">Search above to add ingredients to your formula</div>
                    </div>
                """, unsafe_allow_html=True)
            else:
                # Column headers
                col1, col2, col3, col4, col5 = st.columns([2, 3, 1.5, 1.5, 0.5])
                with col1:
                    st.caption("CAS NUMBER")
                with col2:
                    st.caption("NAME")
                with col3:
                    st.caption("PERCENTAGE")
                with col4:
                    st.caption("STATUS")

                # Ingredient rows
                for i, ing in enumerate(st.session_state.ingredients):
                    col1, col2, col3, col4, col5 = st.columns([2, 3, 1.5, 1.5, 0.5])

                    with col1:
                        new_cas = st.text_input(
                            "CAS", value=ing["cas_number"], key=f"cas_{i}",
                            label_visibility="collapsed",
                        )
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
                            label_visibility="collapsed",
                        )
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
                            "%", value=float(ing["percentage"]), min_value=0.0, max_value=100.0,
                            key=f"pct_{i}", step=0.1,
                            label_visibility="collapsed",
                        )

                    with col4:
                        info = autofill_ingredient(ing["cas_number"])
                        if info:
                            if info.get("allergen") or info.get("ifra_restricted"):
                                badges = []
                                if info.get("allergen"):
                                    badges.append("Allergen")
                                if info.get("ifra_restricted"):
                                    badges.append("IFRA")
                                st.warning(", ".join(badges))
                            else:
                                st.success("Clear")
                        else:
                            st.caption("Unknown")

                    with col5:
                        if st.button("X", key=f"del_{i}", help="Remove ingredient"):
                            st.session_state.ingredients.pop(i)
                            st.rerun()

            # Add manual ingredient button
            if st.button("Add Manual Ingredient"):
                st.session_state.ingredients.append({
                    "cas_number": "",
                    "name": "",
                    "percentage": 0.0,
                })
                st.rerun()

            # Summary metrics
            st.divider()
            total_pct = sum(ing["percentage"] for ing in st.session_state.ingredients)
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total %", f"{total_pct:.1f}%")
            with col2:
                st.metric("Ingredients", len(st.session_state.ingredients))
            with col3:
                allergen_count = sum(1 for ing in st.session_state.ingredients
                                    if autofill_ingredient(ing["cas_number"]) and
                                    autofill_ingredient(ing["cas_number"]).get("allergen"))
                st.metric("Allergens", allergen_count)
            with col4:
                if abs(total_pct - 100.0) <= 0.1:
                    st.success("Formula complete")
                else:
                    st.warning(f"{100 - total_pct:.1f}% remaining")

        with tab2:
            render_progress_steps(1)

            st.markdown("### Compliance Check")

            if not st.session_state.get("ingredients"):
                st.info("Add ingredients in the Formula Input tab first")
            else:
                st.markdown(f"""
                    <div class="info-card">
                        <strong>Ready to check:</strong> {len(st.session_state.ingredients)} ingredients
                        for {', '.join([m.upper() for m in markets])} markets
                    </div>
                """, unsafe_allow_html=True)

                if st.button("Run Full Compliance Check", type="primary", use_container_width=True):
                    engine = get_engine()

                    formula = FormulaData(
                        name=formula_name,
                        ingredients=[
                            FormulaIngredientData(**ing)
                            for ing in st.session_state.ingredients
                            if ing["cas_number"] and ing["percentage"] > 0
                        ],
                    )

                    with st.spinner("Checking compliance across all regulations..."):
                        report = engine.check_compliance(
                            formula=formula,
                            product_type=ProductType(product_type),
                            markets=[Market(m) for m in markets],
                            fragrance_concentration=fragrance_concentration,
                            is_leave_on=is_leave_on,
                        )

                    # Results header
                    if report.is_compliant:
                        st.markdown(f"""
                            <div class="result-compliant">
                                <div style="font-size: 3rem;">&#10003;</div>
                                <h2 style="color: #10b981; margin: 10px 0;">COMPLIANT</h2>
                                <p style="color: #64748b;">Formula meets all regulatory requirements</p>
                                {f'<p><strong>Certificate:</strong> {report.certificate_number}</p>' if report.certificate_number else ''}
                            </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.markdown(f"""
                            <div class="result-non-compliant">
                                <div style="font-size: 3rem;">&#10005;</div>
                                <h2 style="color: #ef4444; margin: 10px 0;">NON-COMPLIANT</h2>
                                <p style="color: #64748b;">Formula has {len(report.non_compliant_items)} violation(s)</p>
                            </div>
                        """, unsafe_allow_html=True)

                    st.divider()

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

                    # Detailed results table
                    with st.expander("View All Results", expanded=False):
                        results_data = [
                            {
                                "Requirement": r.requirement,
                                "Status": r.status.value.upper(),
                                "Market": r.market.value.upper(),
                                "Ingredient": r.ingredient_name or "-",
                                "Details": r.details or "-",
                            }
                            for r in report.results
                        ]
                        st.dataframe(results_data, use_container_width=True)

        with tab3:
            render_progress_steps(2)

            st.markdown("### Generate Documents")

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
                    st.markdown("""
                        <div class="doc-card">
                            <h4>IFRA Certificate of Conformity</h4>
                            <p style="color: #64748b; font-size: 0.9rem;">
                                Certifies compliance with IFRA standards
                            </p>
                        </div>
                    """, unsafe_allow_html=True)
                    signatory_name = st.text_input("Signatory Name", value="Quality Manager", key="sig_name")
                    signatory_title = st.text_input("Signatory Title", value="Quality Assurance", key="sig_title")

                    if st.button("Generate IFRA Certificate", type="primary", key="gen_ifra", use_container_width=True):
                        with st.spinner("Generating PDF..."):
                            pdf_bytes = generate_pdf_document(
                                "ifra-certificate",
                                formula_data,
                                {**common_settings, "signatory_name": signatory_name, "signatory_title": signatory_title},
                            )
                            if pdf_bytes:
                                st.download_button(
                                    "Download IFRA Certificate",
                                    data=pdf_bytes,
                                    file_name=f"IFRA_Certificate_{formula_name}_{datetime.now().strftime('%Y%m%d')}.pdf",
                                    mime="application/pdf",
                                    use_container_width=True,
                                )

                with col2:
                    st.markdown("""
                        <div class="doc-card">
                            <h4>Allergen Declaration</h4>
                            <p style="color: #64748b; font-size: 0.9rem;">
                                Lists allergens requiring disclosure by market
                            </p>
                        </div>
                    """, unsafe_allow_html=True)
                    st.write("")  # Spacing
                    st.write("")
                    if st.button("Generate Allergen Statement", type="primary", key="gen_allergen", use_container_width=True):
                        with st.spinner("Generating PDF..."):
                            pdf_bytes = generate_pdf_document(
                                "allergen-statement",
                                formula_data,
                                common_settings,
                            )
                            if pdf_bytes:
                                st.download_button(
                                    "Download Allergen Statement",
                                    data=pdf_bytes,
                                    file_name=f"Allergen_Statement_{formula_name}_{datetime.now().strftime('%Y%m%d')}.pdf",
                                    mime="application/pdf",
                                    use_container_width=True,
                                )

                st.divider()

                col3, col4 = st.columns(2)

                with col3:
                    st.markdown("""
                        <div class="doc-card">
                            <h4>VOC Compliance Statement</h4>
                            <p style="color: #64748b; font-size: 0.9rem;">
                                CARB and Canada VOC compliance
                            </p>
                        </div>
                    """, unsafe_allow_html=True)
                    if st.button("Generate VOC Statement", type="primary", key="gen_voc", use_container_width=True):
                        with st.spinner("Generating PDF..."):
                            pdf_bytes = generate_pdf_document(
                                "voc-statement",
                                formula_data,
                                common_settings,
                            )
                            if pdf_bytes:
                                st.download_button(
                                    "Download VOC Statement",
                                    data=pdf_bytes,
                                    file_name=f"VOC_Statement_{formula_name}_{datetime.now().strftime('%Y%m%d')}.pdf",
                                    mime="application/pdf",
                                    use_container_width=True,
                                )

                with col4:
                    st.markdown("""
                        <div class="doc-card">
                            <h4>Fragrance Safety Evaluation</h4>
                            <p style="color: #64748b; font-size: 0.9rem;">
                                Complete safety assessment report
                            </p>
                        </div>
                    """, unsafe_allow_html=True)
                    assessor = st.text_input("Assessor Name", value="", key="assessor")
                    intended_use = st.text_area("Intended Use", value="", key="intended_use", height=68)

                    if st.button("Generate FSE Report", type="primary", key="gen_fse", use_container_width=True):
                        with st.spinner("Generating PDF..."):
                            pdf_bytes = generate_pdf_document(
                                "fse",
                                formula_data,
                                {**common_settings, "assessor": assessor, "intended_use": intended_use},
                            )
                            if pdf_bytes:
                                st.download_button(
                                    "Download FSE Report",
                                    data=pdf_bytes,
                                    file_name=f"FSE_{formula_name}_{datetime.now().strftime('%Y%m%d')}.pdf",
                                    mime="application/pdf",
                                    use_container_width=True,
                                )

        with tab4:
            st.markdown("### Formula Library")

            library = get_formula_library()
            formulas = library.list_all()

            # Search
            search = st.text_input("Search formulas...", placeholder="Search by name or tags", key="lib_search")
            if search:
                formulas = library.search(search)

            if not formulas:
                st.markdown("""
                    <div class="empty-state">
                        <div class="empty-icon">&#128218;</div>
                        <div><strong>No formulas saved</strong></div>
                        <div style="font-size: 0.9rem;">Save a formula from the Formula Input tab</div>
                    </div>
                """, unsafe_allow_html=True)
            else:
                st.caption(f"Showing {len(formulas)} formula(s)")

                for formula in formulas:
                    with st.expander(f"{formula.name}", expanded=False):
                        col1, col2 = st.columns([3, 1])

                        with col1:
                            st.caption(f"ID: {formula.id[:8]}... | Updated: {formula.updated_at[:10]}")
                            if formula.description:
                                st.write(formula.description)
                            if formula.tags:
                                st.write("Tags: " + ", ".join(formula.tags))

                            # Ingredients
                            st.write("**Ingredients:**")
                            ing_data = [
                                {"CAS": ing["cas_number"], "Name": ing["name"], "%": ing["percentage"]}
                                for ing in formula.ingredients
                            ]
                            st.dataframe(ing_data, use_container_width=True, hide_index=True)

                        with col2:
                            st.metric("Ingredients", len(formula.ingredients))
                            if formula.compliance_status:
                                if formula.compliance_status == "compliant":
                                    st.success("Compliant")
                                else:
                                    st.error("Non-compliant")

                        # Actions
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            if st.button("Load", key=f"load_{formula.id}", use_container_width=True):
                                st.session_state.ingredients = formula.ingredients.copy()
                                st.session_state.formula_name = formula.name
                                st.success(f"Loaded: {formula.name}")
                                st.rerun()
                        with col2:
                            if st.button("Duplicate", key=f"dup_{formula.id}", use_container_width=True):
                                library.duplicate(formula.id)
                                st.success("Duplicated!")
                                st.rerun()
                        with col3:
                            if st.button("Delete", key=f"del_lib_{formula.id}", use_container_width=True):
                                library.delete(formula.id)
                                st.success("Deleted")
                                st.rerun()

        with tab5:
            st.markdown("### Quick Checks")

            if not st.session_state.get("ingredients"):
                st.info("Add ingredients in the Formula Input tab first")
            else:
                check_type = st.selectbox(
                    "Select Check Type",
                    options=["IFRA Only", "Allergens Only", "VOC Only", "FSE Generation"],
                )

                if st.button("Run Quick Check", type="primary"):
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
                            if result.is_compliant:
                                st.success("IFRA Compliant")
                            else:
                                st.error("IFRA Non-Compliant")
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
