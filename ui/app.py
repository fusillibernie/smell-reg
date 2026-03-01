"""Streamlit-based web interface for smell-reg.

Run with: streamlit run ui/app.py
"""

try:
    import streamlit as st
    import pandas as pd
    import json
    import base64
    STREAMLIT_AVAILABLE = True
except ImportError:
    STREAMLIT_AVAILABLE = False
    print("Streamlit is not installed. Run: pip install streamlit")

if STREAMLIT_AVAILABLE:
    import sys
    from pathlib import Path
    from datetime import datetime
    from tempfile import NamedTemporaryFile

    # Add project root to path
    sys.path.insert(0, str(Path(__file__).parent.parent))

    from src.models.regulatory import Market, ProductType, PRODUCT_TO_IFRA_CATEGORY
    from src.services.compliance_engine import ComplianceEngine
    from src.services.materials_service import MaterialsService
    from src.services.formula_library import FormulaLibrary
    from src.services.allergen_service import AllergenService
    from src.integrations.aroma_lab import FormulaData, FormulaIngredientData
    from src.documents.pdf_generator import PDFGenerator, WEASYPRINT_AVAILABLE

    # IFRA Product Categories for intended use
    IFRA_CATEGORIES = {
        "Cat 1 - Lip Products": "Products applied to the lips (lipstick, lip balm, lip gloss)",
        "Cat 2 - Deodorants/Antiperspirants": "Deodorant and antiperspirant products of all types",
        "Cat 3 - Hydroalcoholic (face)": "Hydroalcoholic products applied to recently shaved skin",
        "Cat 4 - Fine Fragrance": "Fine fragrance, eau de toilette, eau de parfum, parfum",
        "Cat 5A - Body Lotion": "Body lotion, body cream, body oil",
        "Cat 5B - Face Cream": "Face cream, face moisturizer",
        "Cat 5C - Hand Cream": "Hand cream, hand lotion",
        "Cat 5D - Baby Products": "Baby creams, lotions, oils",
        "Cat 6 - Mouthwash/Oral": "Mouthwash, toothpaste, breath fresheners",
        "Cat 7A - Rinse-off Hair": "Shampoo, conditioner, hair treatments",
        "Cat 7B - Leave-on Hair": "Hair styling products, hair spray",
        "Cat 8 - Intimate Products": "Intimate wipes and deodorants",
        "Cat 9 - Rinse-off Body": "Body wash, shower gel, bar soap",
        "Cat 10A - Household Aerosol": "Aerosol air fresheners",
        "Cat 10B - Household Non-Aerosol": "Non-aerosol cleaners, detergents",
        "Cat 11A - Candles": "Scented candles",
        "Cat 11B - Reed Diffusers": "Reed diffusers, potpourri",
        "Cat 12 - Other Air Care": "Other air fresheners, incense",
    }

    # Settings file path
    SETTINGS_FILE = Path(__file__).parent.parent / "data" / "settings.json"

    # Modern CSS
    CUSTOM_CSS = """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

        .main .block-container {
            padding: 1.5rem 2rem;
            max-width: 1400px;
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        }

        .app-header {
            background: linear-gradient(135deg, #059669 0%, #10b981 100%);
            padding: 1.5rem 2rem;
            border-radius: 12px;
            margin-bottom: 1.5rem;
            color: white;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .app-title { font-size: 1.8rem; font-weight: 700; margin: 0; letter-spacing: -0.5px; }
        .app-subtitle { font-size: 0.85rem; opacity: 0.9; margin-top: 4px; }
        .header-stats { display: flex; gap: 24px; }
        .header-stat { text-align: center; }
        .header-stat-value { font-size: 1.5rem; font-weight: 700; }
        .header-stat-label { font-size: 0.7rem; opacity: 0.8; text-transform: uppercase; letter-spacing: 0.5px; }

        .card {
            background: rgba(255,255,255,0.03);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 12px;
            padding: 1.25rem;
            margin-bottom: 1rem;
        }
        .card-header {
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: #94a3b8;
            margin-bottom: 0.75rem;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .allergen-box {
            background: linear-gradient(135deg, rgba(239, 68, 68, 0.15) 0%, rgba(239, 68, 68, 0.08) 100%);
            border: 1px solid rgba(239, 68, 68, 0.3);
            border-radius: 12px;
            padding: 1rem 1.25rem;
            margin: 1rem 0;
        }
        .allergen-box-title { font-size: 0.8rem; font-weight: 600; color: #f87171; margin-bottom: 8px; display: flex; align-items: center; gap: 6px; }
        .allergen-box-content { font-size: 0.9rem; color: #fca5a5; line-height: 1.6; }
        .allergen-tag { display: inline-block; background: rgba(239, 68, 68, 0.2); padding: 3px 10px; border-radius: 20px; margin: 3px 4px 3px 0; font-size: 0.8rem; color: #fca5a5; }

        .warning-box {
            background: linear-gradient(135deg, rgba(245, 158, 11, 0.15) 0%, rgba(245, 158, 11, 0.08) 100%);
            border: 1px solid rgba(245, 158, 11, 0.3);
            border-radius: 12px;
            padding: 1rem 1.25rem;
            margin: 1rem 0;
        }
        .warning-box-title { font-size: 0.8rem; font-weight: 600; color: #fbbf24; margin-bottom: 8px; }
        .warning-box-content { font-size: 0.9rem; color: #fcd34d; }

        .success-box {
            background: linear-gradient(135deg, rgba(16, 185, 129, 0.15) 0%, rgba(16, 185, 129, 0.08) 100%);
            border: 1px solid rgba(16, 185, 129, 0.3);
            border-radius: 12px;
            padding: 1rem 1.25rem;
            margin: 1rem 0;
        }
        .success-box-title { font-size: 0.8rem; font-weight: 600; color: #34d399; }

        .metric-card {
            flex: 1;
            background: rgba(255,255,255,0.03);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 10px;
            padding: 1rem;
            text-align: center;
        }
        .metric-value { font-size: 1.5rem; font-weight: 700; color: #10b981; }
        .metric-label { font-size: 0.7rem; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; margin-top: 4px; }
        .metric-card.warning .metric-value { color: #f59e0b; }
        .metric-card.error .metric-value { color: #ef4444; }

        .stButton > button { border-radius: 8px; font-weight: 500; transition: all 0.2s; }
        .stButton > button:hover { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(0,0,0,0.15); }

        .stTextInput > div > div > input, .stNumberInput > div > div > input {
            border-radius: 8px;
            border: 1px solid rgba(255,255,255,0.1);
            background: rgba(255,255,255,0.03);
        }

        .stSelectbox [data-baseweb="select"] { border-radius: 8px; }
        .stSelectbox [data-baseweb="select"] > div { font-size: 0.9rem; min-height: 38px; }

        .stTabs [data-baseweb="tab-list"] { gap: 8px; background: rgba(255,255,255,0.03); padding: 4px; border-radius: 10px; }
        .stTabs [data-baseweb="tab"] { border-radius: 8px; padding: 10px 20px; font-weight: 500; }
        .stTabs [aria-selected="true"] { background: #10b981 !important; }

        [data-testid="stDataEditor"] { border-radius: 10px; overflow: hidden; }
        .streamlit-expanderHeader { font-size: 0.85rem; font-weight: 600; }

        #MainMenu, footer, header { visibility: hidden; }
        .stDeployButton { display: none; }
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

    @st.cache_resource
    def get_allergen_service():
        return AllergenService()

    @st.cache_resource
    def get_pdf_generator():
        return PDFGenerator() if WEASYPRINT_AVAILABLE else None

    def load_settings() -> dict:
        """Load company settings from file."""
        defaults = {
            "company_name": "Fragrance Company",
            "company_address": "",
            "company_phone": "",
            "company_email": "",
            "company_website": "",
            "logo_base64": None,
        }
        if SETTINGS_FILE.exists():
            try:
                with open(SETTINGS_FILE, "r") as f:
                    saved = json.load(f)
                    defaults.update(saved)
            except:
                pass
        return defaults

    def save_settings(settings: dict):
        """Save company settings to file."""
        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(SETTINGS_FILE, "w") as f:
            json.dump(settings, f, indent=2)

    @st.cache_data
    def get_all_materials_for_autocomplete():
        """Get all materials formatted for autocomplete dropdown."""
        materials = get_materials_service()
        all_mats = materials.get_all()
        options = []
        for m in all_mats:
            label = f"{m.name} ({m.cas_number})"
            options.append({
                "label": label,
                "cas_number": m.cas_number,
                "name": m.name,
                "allergen": m.allergen,
                "ifra_restricted": m.ifra_restricted,
            })
        return options

    def get_live_allergen_check(ingredients: list, frag_conc: float = 100.0, is_leave_on: bool = True) -> dict:
        """Run live allergen check on current ingredients."""
        if not ingredients:
            return {"allergens": [], "requiring_disclosure": [], "count": 0}

        try:
            engine = get_engine()
            valid_ingredients = [
                ing for ing in ingredients
                if ing.get("cas_number") and ing.get("percentage", 0) > 0
            ]

            if not valid_ingredients:
                return {"allergens": [], "requiring_disclosure": [], "count": 0}

            formula = FormulaData(
                name="Live Check",
                ingredients=[FormulaIngredientData(**ing) for ing in valid_ingredients],
            )

            report = engine.check_allergens(
                formula=formula,
                markets=[Market.EU],
                fragrance_concentration=frag_conc,
                is_leave_on=is_leave_on,
            )

            return {
                "allergens": [a.name for a in report.detected_allergens],
                "requiring_disclosure": [a.name for a in report.disclosure_required],
                "count": len(report.detected_allergens),
                "disclosure_count": len(report.disclosure_required),
                "details": [
                    {
                        "name": a.name,
                        "cas": a.cas_number,
                        "pct_in_frag": round(a.concentration_in_fragrance, 4),
                        "pct_in_prod": round(a.concentration_in_product, 4),
                        "requires_disclosure": a.requires_disclosure,
                        "source": a.source_details or "Direct",
                    }
                    for a in report.detected_allergens
                ],
            }
        except Exception as e:
            return {"allergens": [], "requiring_disclosure": [], "count": 0, "error": str(e)}

    def generate_pdf_document(doc_type: str, formula_data: dict, settings: dict, metadata: dict, company_settings: dict) -> tuple:
        """Generate PDF document."""
        if not WEASYPRINT_AVAILABLE:
            st.error("WeasyPrint is not installed. Run: pip install weasyprint")
            return None, None

        try:
            engine = get_engine()
            pdf_gen = get_pdf_generator()

            # Update PDF generator with company settings
            pdf_gen.company_name = company_settings.get("company_name", "Fragrance Company")

            formula = FormulaData(
                name=formula_data["name"],
                ingredients=[FormulaIngredientData(**ing) for ing in formula_data["ingredients"]],
            )

            product_type = ProductType(settings.get("product_type", "fine_fragrance"))
            markets = [Market(m) for m in settings.get("markets", ["us"])]
            frag_conc = settings.get("fragrance_concentration", 100.0)
            is_leave_on = settings.get("is_leave_on", True)

            # Build filename
            parts = []
            if metadata.get("formula_code"):
                parts.append(metadata["formula_code"])
            if metadata.get("brand"):
                parts.append(metadata["brand"].replace(" ", "-"))
            parts.append(formula_data["name"].replace(" ", "-"))
            if metadata.get("version"):
                parts.append(f"v{metadata['version']}")
            parts.append(datetime.now().strftime("%Y%m%d"))

            doc_prefixes = {
                "ifra-certificate": "IFRA",
                "allergen-statement": "Allergen",
                "voc-statement": "VOC",
                "fse": "FSE",
            }
            prefix = doc_prefixes.get(doc_type, "DOC")
            filename = f"{prefix}_{'_'.join(parts)}.pdf"

            with NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                output_path = Path(tmp.name)

            # Pass metadata to PDF generator for footer
            doc_metadata = {
                "formula_code": metadata.get("formula_code", ""),
                "formula_name": formula_data["name"],
                "version": metadata.get("version", "1"),
                "date_created": metadata.get("date_created", datetime.now().strftime("%Y-%m-%d")),
                "company_settings": company_settings,
            }

            if doc_type == "ifra-certificate":
                report = engine.check_compliance(
                    formula=formula,
                    product_type=product_type,
                    markets=markets,
                    fragrance_concentration=frag_conc,
                    is_leave_on=is_leave_on,
                )
                # Calculate max use levels for each IFRA category
                from src.services.ifra_service import IFRAService
                ifra_service = IFRAService()
                max_use_levels = ifra_service.calculate_max_use_levels(formula, include_incidentals=True)

                pdf_gen.generate_ifra_certificate(
                    report=report,
                    output_path=output_path,
                    signatory_name=settings.get("signatory_name"),
                    signatory_title=settings.get("signatory_title"),
                    metadata=doc_metadata,
                    max_use_levels=max_use_levels,
                )
            elif doc_type == "allergen-statement":
                report = engine.check_allergens(
                    formula=formula,
                    markets=markets,
                    fragrance_concentration=frag_conc,
                    is_leave_on=is_leave_on,
                )
                pdf_gen.generate_allergen_statement(report=report, output_path=output_path, metadata=doc_metadata)
            elif doc_type == "voc-statement":
                report = engine.check_voc(formula=formula, product_type=product_type, markets=markets)
                pdf_gen.generate_voc_statement(report=report, output_path=output_path, metadata=doc_metadata)
            elif doc_type == "fse":
                report = engine.generate_fse(
                    formula=formula,
                    product_type=product_type,
                    fragrance_concentration=frag_conc,
                    intended_use=settings.get("intended_use", ""),
                    assessor=settings.get("assessor"),
                )
                pdf_gen.generate_fse(report=report, output_path=output_path, metadata=doc_metadata)
            else:
                return None, None

            with open(output_path, "rb") as f:
                pdf_bytes = f.read()
            output_path.unlink()
            return pdf_bytes, filename

        except Exception as e:
            st.error(f"Error generating PDF: {e}")
            import traceback
            st.code(traceback.format_exc())
            return None, None

    def main():
        st.set_page_config(
            page_title="Smell-Reg | Fragrance Regulatory Compliance",
            page_icon="🧪",
            layout="wide",
            initial_sidebar_state="collapsed",
        )
        st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

        # Load settings
        company_settings = load_settings()

        # Initialize session state
        defaults = {
            "ingredients": [],
            "formula_name": "New Formula",
            "formula_code": "",
            "brand": "",
            "version": "1",
            "date_created": datetime.now().strftime("%Y-%m-%d"),
        }
        for key, val in defaults.items():
            if key not in st.session_state:
                st.session_state[key] = val

        materials_service = get_materials_service()
        formula_library = get_formula_library()

        # Header
        st.markdown(f"""
        <div class="app-header">
            <div>
                <div class="app-title">🧪 Smell-Reg</div>
                <div class="app-subtitle">{company_settings.get('company_name', 'Fragrance Regulatory Compliance')}</div>
            </div>
            <div class="header-stats">
                <div class="header-stat">
                    <div class="header-stat-value">{materials_service.get_count()}</div>
                    <div class="header-stat-label">Materials</div>
                </div>
                <div class="header-stat">
                    <div class="header-stat-value">{formula_library.get_count()}</div>
                    <div class="header-stat-label">Formulas</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Sidebar
        with st.sidebar:
            st.markdown("### ⚙️ Product Settings")
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
            is_leave_on = st.toggle("Leave-on Product", value=True)

            st.divider()
            st.markdown("### 📁 Quick Actions")
            if st.button("📋 Load Sample Formula", use_container_width=True):
                st.session_state.ingredients = [
                    {"cas_number": "115-95-7", "name": "Linalyl Acetate", "percentage": 20.0},
                    {"cas_number": "78-70-6", "name": "Linalool", "percentage": 15.0},
                    {"cas_number": "106-22-9", "name": "Citronellol", "percentage": 10.0},
                    {"cas_number": "106-24-1", "name": "Geraniol", "percentage": 8.0},
                    {"cas_number": "101-86-0", "name": "Hexyl Cinnamal", "percentage": 5.0},
                    {"cas_number": "121-33-5", "name": "Vanillin", "percentage": 3.0},
                    {"cas_number": "8008-56-8", "name": "Lemon Oil", "percentage": 5.0},
                    {"cas_number": "8008-57-9", "name": "Orange Oil Sweet", "percentage": 4.0},
                ]
                st.session_state.formula_name = "Sample Citrus Floral"
                st.session_state.formula_code = "SCF-001"
                st.rerun()

            if st.button("🗑️ Clear Formula", use_container_width=True):
                st.session_state.ingredients = []
                st.session_state.formula_name = "New Formula"
                st.session_state.formula_code = ""
                st.rerun()

        # Main tabs (consolidated Compliance into Formula)
        tab1, tab3, tab4, tab5 = st.tabs(["📝 Formula & Compliance", "📄 Documents", "📚 Library", "⚙️ Settings"])

        # ==================== FORMULA TAB ====================
        with tab1:
            # Load existing formula
            st.markdown('<div class="card-header">📂 Load Existing Formula</div>', unsafe_allow_html=True)
            formulas = formula_library.list_all()
            formula_options = ["-- Select --"] + [f"{f.name}" for f in formulas]

            col1, col2 = st.columns([4, 1])
            with col1:
                selected_formula = st.selectbox("Load", options=formula_options, label_visibility="collapsed", key="load_formula")
            with col2:
                if st.button("Load", use_container_width=True, disabled=selected_formula == "-- Select --"):
                    idx = formula_options.index(selected_formula) - 1
                    if idx >= 0:
                        f = formulas[idx]
                        st.session_state.ingredients = f.ingredients.copy()
                        st.session_state.formula_name = f.name
                        st.rerun()

            st.markdown("---")

            # Formula metadata
            st.markdown('<div class="card-header">📋 Formula Information</div>', unsafe_allow_html=True)
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.session_state.formula_code = st.text_input("Formula Code", value=st.session_state.formula_code, placeholder="FRG-2024-001")
            with col2:
                st.session_state.formula_name = st.text_input("Formula Name", value=st.session_state.formula_name)
            with col3:
                st.session_state.brand = st.text_input("Brand / Customer", value=st.session_state.brand)
            with col4:
                vcol1, vcol2 = st.columns(2)
                with vcol1:
                    st.session_state.version = st.text_input("Version", value=st.session_state.version)
                with vcol2:
                    st.session_state.date_created = st.text_input("Date", value=st.session_state.date_created)

            # Save/Export
            col1, col2, col3 = st.columns([1, 1, 4])
            with col1:
                if st.button("💾 Save", type="primary", use_container_width=True):
                    if st.session_state.ingredients:
                        formula_library.save(
                            name=st.session_state.formula_name,
                            ingredients=st.session_state.ingredients,
                            description=f"Code: {st.session_state.formula_code}, Brand: {st.session_state.brand}, v{st.session_state.version}",
                        )
                        st.success("✅ Saved!")
                    else:
                        st.warning("Add ingredients first")
            with col2:
                if st.session_state.ingredients:
                    csv = "CAS,Name,Percentage\n"
                    for ing in st.session_state.ingredients:
                        csv += f'"{ing.get("cas_number", "")}","{ing.get("name", "")}",{ing.get("percentage", 0)}\n'
                    st.download_button("📥 CSV", csv, f"{st.session_state.formula_name}.csv", "text/csv", use_container_width=True)

            st.markdown("---")

            # Add ingredient
            st.markdown('<div class="card-header">➕ Add Ingredient</div>', unsafe_allow_html=True)
            all_materials = get_all_materials_for_autocomplete()
            material_options = [""] + [m["label"] for m in all_materials]

            with st.form(key="add_ingredient_form", clear_on_submit=True):
                col1, col2, col3 = st.columns([5, 1, 1])
                with col1:
                    selected = st.selectbox("Material", options=material_options, format_func=lambda x: x if x else "🔍 Search...", label_visibility="collapsed")
                with col2:
                    add_pct = st.number_input("%", value=1.0, min_value=0.01, max_value=100.0, step=0.1, label_visibility="collapsed")
                with col3:
                    submitted = st.form_submit_button("Add", use_container_width=True)

                if submitted and selected:
                    for m in all_materials:
                        if m["label"] == selected:
                            existing = [i["cas_number"] for i in st.session_state.ingredients]
                            if m["cas_number"] not in existing:
                                st.session_state.ingredients.append({
                                    "cas_number": m["cas_number"],
                                    "name": m["name"],
                                    "percentage": add_pct,
                                })
                                st.rerun()
                            else:
                                st.warning("⚠️ Already in formula")
                            break

            # Live allergen display
            if st.session_state.ingredients:
                allergen_check = get_live_allergen_check(
                    st.session_state.ingredients,
                    frag_conc=fragrance_concentration,
                    is_leave_on=is_leave_on,
                )

                if allergen_check.get("error"):
                    st.warning(f"Allergen check error: {allergen_check['error']}")
                elif allergen_check.get("requiring_disclosure"):
                    tags = "".join([f'<span class="allergen-tag">{name}</span>' for name in allergen_check["requiring_disclosure"]])
                    st.markdown(f"""
                    <div class="allergen-box">
                        <div class="allergen-box-title">⚠️ Allergens Requiring Disclosure ({allergen_check['disclosure_count']})</div>
                        <div class="allergen-box-content">{tags}</div>
                    </div>
                    """, unsafe_allow_html=True)
                elif allergen_check.get("allergens"):
                    st.markdown(f"""
                    <div class="warning-box">
                        <div class="warning-box-title">ℹ️ Allergens Detected (below threshold)</div>
                        <div class="warning-box-content">{', '.join(allergen_check['allergens'])}</div>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown("""
                    <div class="success-box">
                        <div class="success-box-title">✅ No allergens requiring disclosure</div>
                    </div>
                    """, unsafe_allow_html=True)

                if allergen_check.get("details"):
                    with st.expander(f"📊 Allergen Details ({len(allergen_check['details'])} found)"):
                        detail_df = pd.DataFrame(allergen_check["details"])
                        detail_df.columns = ["Allergen", "CAS", "% in Fragrance", "% in Product", "Requires Disclosure", "Source"]
                        st.dataframe(detail_df, use_container_width=True, hide_index=True)

            st.markdown("---")

            # Ingredients table
            st.markdown('<div class="card-header">🧴 Formula Ingredients</div>', unsafe_allow_html=True)
            if not st.session_state.ingredients:
                st.info("No ingredients yet. Use search above or load a sample.")
            else:
                df = pd.DataFrame(st.session_state.ingredients)
                edited_df = st.data_editor(
                    df,
                    column_config={
                        "cas_number": st.column_config.TextColumn("CAS Number", width="medium"),
                        "name": st.column_config.TextColumn("Material Name", width="large"),
                        "percentage": st.column_config.NumberColumn("%", min_value=0.0, max_value=100.0, step=0.01, format="%.2f"),
                    },
                    hide_index=True,
                    use_container_width=True,
                    num_rows="dynamic",
                    key="ingredient_editor",
                )
                st.session_state.ingredients = edited_df.to_dict('records')

                # Metrics
                total_pct = sum(ing.get("percentage", 0) for ing in st.session_state.ingredients)
                allergen_count = allergen_check.get("disclosure_count", 0) if 'allergen_check' in dir() else 0

                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    status_class = "" if abs(total_pct - 100) <= 0.5 else "warning" if total_pct < 100 else "error"
                    st.markdown(f'<div class="metric-card {status_class}"><div class="metric-value">{total_pct:.1f}%</div><div class="metric-label">Total</div></div>', unsafe_allow_html=True)
                with col2:
                    st.markdown(f'<div class="metric-card"><div class="metric-value">{len(st.session_state.ingredients)}</div><div class="metric-label">Ingredients</div></div>', unsafe_allow_html=True)
                with col3:
                    ac_class = "error" if allergen_count > 0 else ""
                    st.markdown(f'<div class="metric-card {ac_class}"><div class="metric-value">{allergen_count}</div><div class="metric-label">Allergens</div></div>', unsafe_allow_html=True)
                with col4:
                    if abs(total_pct - 100) <= 0.5:
                        st.markdown('<div class="metric-card"><div class="metric-value" style="color:#10b981;">✓</div><div class="metric-label">Complete</div></div>', unsafe_allow_html=True)
                    else:
                        diff = 100 - total_pct
                        st.markdown(f'<div class="metric-card warning"><div class="metric-value">{diff:+.1f}%</div><div class="metric-label">Remaining</div></div>', unsafe_allow_html=True)

                if st.button("⚖️ Normalize to 100%", disabled=total_pct == 0):
                    factor = 100.0 / total_pct
                    for ing in st.session_state.ingredients:
                        ing["percentage"] = round(ing["percentage"] * factor, 2)
                    st.rerun()

                # ==================== COMPLIANCE CHECK (embedded) ====================
                st.markdown("---")
                st.markdown('<div class="card-header">✅ Compliance Check</div>', unsafe_allow_html=True)

                if st.button("🔍 Run Full Compliance Check", type="primary", use_container_width=True):
                    engine = get_engine()
                    formula = FormulaData(
                        name=st.session_state.formula_name,
                        ingredients=[FormulaIngredientData(**ing) for ing in st.session_state.ingredients if ing.get("cas_number") and ing.get("percentage", 0) > 0],
                    )

                    with st.spinner("Checking..."):
                        report = engine.check_compliance(
                            formula=formula,
                            product_type=ProductType(product_type),
                            markets=[Market(m) for m in markets],
                            fragrance_concentration=fragrance_concentration,
                            is_leave_on=is_leave_on,
                        )

                    if report.is_compliant:
                        st.success(f"✅ **COMPLIANT** | Certificate: {report.certificate_number}")
                    else:
                        st.error(f"❌ **NON-COMPLIANT** | {len(report.non_compliant_items)} violation(s)")

                    if report.non_compliant_items:
                        st.markdown("##### ❌ Violations")
                        for v in report.non_compliant_items:
                            st.error(f"**{v.ingredient_name or v.requirement}**: {v.details}")

                    if report.warnings:
                        st.markdown("##### ⚠️ Warnings")
                        for w in report.warnings:
                            st.warning(f"**{w.ingredient_name or w.requirement}**: {w.details}")

                    with st.expander("📊 All Compliance Results"):
                        results_df = pd.DataFrame([{
                            "Requirement": r.requirement,
                            "Status": r.status.value.upper(),
                            "Market": r.market.value.upper(),
                            "Ingredient": r.ingredient_name or "-",
                            "Details": r.details or "-",
                        } for r in report.results])
                        st.dataframe(results_df, use_container_width=True, hide_index=True)

        # ==================== DOCUMENTS TAB ====================
        with tab3:
            st.markdown("### 📄 Generate Documents")
            st.caption("Documents named: [Type]_[Code]_[Brand]_[Name]_[Version]_[Date].pdf")

            if not st.session_state.ingredients:
                st.info("Add ingredients first")
            else:
                formula_data = {
                    "name": st.session_state.formula_name,
                    "ingredients": [ing for ing in st.session_state.ingredients if ing.get("cas_number") and ing.get("percentage", 0) > 0],
                }
                metadata = {
                    "formula_code": st.session_state.formula_code,
                    "brand": st.session_state.brand,
                    "version": st.session_state.version,
                    "date_created": st.session_state.date_created,
                }
                common_settings = {
                    "product_type": product_type,
                    "markets": markets,
                    "fragrance_concentration": fragrance_concentration,
                    "is_leave_on": is_leave_on,
                }

                col1, col2 = st.columns(2)

                with col1:
                    st.markdown("#### 📜 IFRA Certificate")
                    sig_name = st.text_input("Signatory Name", value="Quality Manager", key="sig_name")
                    sig_title = st.text_input("Signatory Title", value="QA Manager", key="sig_title")
                    if st.button("Generate IFRA Certificate", use_container_width=True):
                        with st.spinner("Generating..."):
                            pdf, filename = generate_pdf_document(
                                "ifra-certificate", formula_data,
                                {**common_settings, "signatory_name": sig_name, "signatory_title": sig_title},
                                metadata, company_settings
                            )
                            if pdf:
                                st.download_button(f"📥 {filename}", pdf, filename, "application/pdf", use_container_width=True)

                with col2:
                    st.markdown("#### 🏷️ Allergen Statement")
                    st.write("")
                    st.write("")
                    if st.button("Generate Allergen Statement", use_container_width=True):
                        with st.spinner("Generating..."):
                            pdf, filename = generate_pdf_document("allergen-statement", formula_data, common_settings, metadata, company_settings)
                            if pdf:
                                st.download_button(f"📥 {filename}", pdf, filename, "application/pdf", use_container_width=True)

                st.markdown("---")

                col3, col4 = st.columns(2)

                with col3:
                    st.markdown("#### 🌿 VOC Statement")
                    if st.button("Generate VOC Statement", use_container_width=True):
                        with st.spinner("Generating..."):
                            pdf, filename = generate_pdf_document("voc-statement", formula_data, common_settings, metadata, company_settings)
                            if pdf:
                                st.download_button(f"📥 {filename}", pdf, filename, "application/pdf", use_container_width=True)

                with col4:
                    st.markdown("#### 📋 FSE Report")
                    assessor = st.text_input("Assessor Name", key="assessor")
                    # Use IFRA categories for intended use
                    intended_use = st.selectbox(
                        "Intended Use (IFRA Category)",
                        options=list(IFRA_CATEGORIES.keys()),
                        format_func=lambda x: x,
                        key="intended_use_select",
                    )
                    if st.button("Generate FSE Report", use_container_width=True):
                        with st.spinner("Generating..."):
                            pdf, filename = generate_pdf_document(
                                "fse", formula_data,
                                {**common_settings, "assessor": assessor, "intended_use": intended_use},
                                metadata, company_settings
                            )
                            if pdf:
                                st.download_button(f"📥 {filename}", pdf, filename, "application/pdf", use_container_width=True)

        # ==================== LIBRARY TAB ====================
        with tab4:
            st.markdown("### 📚 Formula Library")

            search = st.text_input("🔍 Search...", key="lib_search", placeholder="Search by name...")
            formulas = formula_library.search(search) if search else formula_library.list_all()

            if not formulas:
                st.info("No saved formulas")
            else:
                for f in formulas:
                    version_badge = f"v{f.current_version}" if hasattr(f, 'current_version') and f.current_version else "v1"
                    with st.expander(f"📋 {f.name} ({len(f.ingredients)} ingredients) • {version_badge}"):
                        if f.description:
                            st.caption(f.description)
                        if f.ingredients:
                            st.dataframe(pd.DataFrame(f.ingredients), use_container_width=True, hide_index=True)

                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            if st.button("📂 Load", key=f"load_{f.id}", use_container_width=True):
                                st.session_state.ingredients = f.ingredients.copy()
                                st.session_state.formula_name = f.name
                                st.rerun()
                        with col2:
                            if st.button("📋 Duplicate", key=f"dup_{f.id}", use_container_width=True):
                                formula_library.duplicate(f.id)
                                st.rerun()
                        with col3:
                            if st.button("📜 History", key=f"hist_{f.id}", use_container_width=True):
                                st.session_state[f"show_history_{f.id}"] = not st.session_state.get(f"show_history_{f.id}", False)
                                st.rerun()
                        with col4:
                            if st.button("🗑️ Delete", key=f"del_{f.id}", use_container_width=True):
                                formula_library.delete(f.id)
                                st.rerun()

                        # Version History Section
                        if st.session_state.get(f"show_history_{f.id}", False):
                            st.markdown("---")
                            st.markdown("##### 📜 Version History")

                            versions = formula_library.get_version_history(f.id)
                            if not versions:
                                st.info("No version history available")
                            else:
                                for v in versions:
                                    is_current = v.version == f.current_version
                                    version_label = f"**v{v.version}** {'(current)' if is_current else ''}"
                                    timestamp = v.timestamp[:10] if v.timestamp else "Unknown"

                                    vcol1, vcol2, vcol3 = st.columns([2, 4, 2])
                                    with vcol1:
                                        st.markdown(version_label)
                                        st.caption(timestamp)
                                    with vcol2:
                                        st.caption(v.change_summary or "No changes recorded")
                                        # Show detailed changes
                                        if v.changes:
                                            change_details = []
                                            for c in v.changes[:3]:  # Show first 3 changes
                                                change_details.append(f"• {c.get('details', '')}")
                                            if len(v.changes) > 3:
                                                change_details.append(f"• ... and {len(v.changes) - 3} more")
                                            st.caption("\n".join(change_details))
                                    with vcol3:
                                        if not is_current:
                                            if st.button("↩️ Restore", key=f"restore_{f.id}_{v.version}", use_container_width=True):
                                                formula_library.restore_version(f.id, v.version)
                                                st.success(f"Restored to v{v.version}")
                                                st.rerun()

                                    st.markdown("---")

        # ==================== SETTINGS TAB ====================
        with tab5:
            st.markdown("### ⚙️ Company Settings")
            st.caption("Configure your company information for document headers and footers.")

            st.markdown("#### 🏢 Company Information")
            col1, col2 = st.columns(2)

            with col1:
                new_company_name = st.text_input("Company Name", value=company_settings.get("company_name", ""))
                new_address = st.text_area("Address", value=company_settings.get("company_address", ""), height=100)
                new_phone = st.text_input("Phone", value=company_settings.get("company_phone", ""))

            with col2:
                new_email = st.text_input("Email", value=company_settings.get("company_email", ""))
                new_website = st.text_input("Website", value=company_settings.get("company_website", ""))

            st.markdown("#### 🖼️ Company Logo")
            uploaded_logo = st.file_uploader("Upload Logo (PNG, JPG)", type=["png", "jpg", "jpeg"])

            if uploaded_logo:
                logo_bytes = uploaded_logo.read()
                logo_base64 = base64.b64encode(logo_bytes).decode()
                st.image(logo_bytes, width=200)
                company_settings["logo_base64"] = logo_base64

            if company_settings.get("logo_base64") and not uploaded_logo:
                st.caption("Current logo:")
                try:
                    logo_data = base64.b64decode(company_settings["logo_base64"])
                    st.image(logo_data, width=200)
                except:
                    pass

                if st.button("Remove Logo"):
                    company_settings["logo_base64"] = None
                    save_settings(company_settings)
                    st.rerun()

            st.markdown("---")

            if st.button("💾 Save Settings", type="primary"):
                company_settings.update({
                    "company_name": new_company_name,
                    "company_address": new_address,
                    "company_phone": new_phone,
                    "company_email": new_email,
                    "company_website": new_website,
                })
                save_settings(company_settings)
                st.success("✅ Settings saved!")
                st.rerun()

    if __name__ == "__main__":
        main()
