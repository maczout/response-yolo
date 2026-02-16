# Response-YOLO Development Strategy

## Vision

Build a command-line reinforced concrete sectional analysis tool that replicates R2K functionality with strict adherence to academic research (Bentz thesis). The tool will be accessible through both natural language (Claude/MCP) and web-based (Streamlit) interfaces.

## Strategic Principles

1. **R2K is the specification** - We're building a clone, not inventing new analysis methods
2. **Validation via differential testing** - Compare outputs against R2K, not experimental data
3. **Academic rigor** - Implementation follows Bentz thesis for theoretical correctness
4. **Incremental feature parity** - Build complete analysis types one at a time, not all features partially
5. **Accessible interfaces** - Engineers shouldn't need to write JSON files to use this tool

## Current State (February 2025)

### ✅ Implemented
- M-φ (moment-curvature) analysis engine with Newton-Raphson solver
- Material models: Popovics/Hognestad/Collins-Mitchell concrete, trilinear steel, Ramberg-Osgood prestressing
- Cross-section geometry: rectangular, T-section, circular, generic shapes
- MCFT biaxial node solver with compression softening
- 3-DOF section integration (ε₀, φ, γxy₀)
- Longitudinal Stiffness Method for shear stress distribution
- Transverse reinforcement modeling (stirrups)
- R2T file parser for section definition
- 73 passing unit tests

### ⚠️ Partially Implemented
- V-γ shear analysis (solver framework exists, needs integration)
- CLI with basic functionality

### ❌ Not Yet Implemented
- Coupled M-V-φ-γ analysis
- R2K output format parity
- Visualization/plotting capabilities
- Streamlit web interface
- MCP server for Claude integration
- Validation test suite against R2K results

## Reverse Engineering R2K (Discovery Phase)

### Objectives
Build a complete specification of R2K's behavior by systematic observation and documentation.

### Tasks

#### 1. Feature Catalog Creation
**Owner:** Jamie (manual work, cannot be delegated to Code)

**Process:**
1. Install R2K and run example analyses
2. Document every input field and its validation rules
3. Identify all analysis types and their options
4. Screenshot complete workflows from section definition to results
5. Export all available output formats

**Deliverables:**
- `docs/r2k_feature_matrix.md` - Structured catalog of all R2K features
- `docs/r2k_workflows/` - Screenshots of UI workflows
- `test_data/r2k_outputs/` - Sample output files for validation

**Key Questions to Answer:**
- What material models does R2K support? What parameters?
- How does R2K define sections? What shapes are available?
- What coordinate systems does R2K use?
- What analysis types exist? What are their inputs/outputs?
- What summary statistics does R2K compute?
- What charts does R2K generate?
- What file formats can R2K import/export?

#### 2. Output Format Specification
**Owner:** Jamie with Claude assistance

**Process:**
1. Run identical analysis in R2K multiple times with different inputs
2. Export results in all available formats (CSV, reports, charts)
3. Reverse-engineer the data schema and formatting rules
4. Document any computed fields (e.g., ductility ratios, capacity reduction factors)

**Deliverables:**
- `docs/r2k_output_formats.md` - Complete specification of output data structures
- `test_data/r2k_baseline/` - Reference outputs for validation suite

#### 3. Validation Test Case Library
**Owner:** Jamie with Code assistance

**Process:**
1. Create diverse test cases spanning R2K's capability range:
   - Simple cases (rectangular sections, uniform reinforcement)
   - Complex cases (T-sections, irregular geometry, prestressing)
   - Edge cases (minimal reinforcement, high strength materials)
2. Run each case in R2K and save outputs
3. Document expected behavior and failure modes

**Deliverables:**
- `test_data/validation_cases/` - Suite of 10-20 test cases with R2K reference outputs
- `docs/validation_test_plan.md` - Test case descriptions and acceptance criteria

## Implementation Roadmap

### Phase 1: M-φ Output Parity (Week 1-2)

**Goal:** Response-YOLO produces identical M-φ results to R2K

**Prerequisites:**
- R2K feature catalog complete
- At least 5 M-φ validation cases documented

**Tasks:**

#### 1.1 Output Format Implementation
**Owner:** Code
```
Implement R2K-compatible output formats for M-φ analysis:
- CSV export matching R2K column structure exactly
- Summary statistics computation (φ_y, M_n, ductility, etc.)
- Event detection reporting (cracking, yielding, ultimate)
- Follow format specification in docs/r2k_output_formats.md
```

**Files to modify:**
- `analysis/moment_curvature.py` - Add output formatting methods
- `io/output.py` - New module for structured output generation
- Update CLI to support R2K output mode

**Validation:** Automated comparison of Response-YOLO vs R2K CSV outputs

#### 1.2 Visualization Module
**Owner:** Code
```
Build plotting module that replicates R2K charts for M-φ analysis:
- M-φ curve with event markers (cracking, yield, ultimate)
- Strain profile diagrams at key curvatures
- Stress block visualization
- Use matplotlib with style matching R2K aesthetics
- Export to PNG/PDF
```

**Files to create:**
- `visualization/plots.py` - Core plotting functions
- `visualization/section_drawing.py` - Cross-section visualization
- `visualization/themes.py` - R2K-style formatting

**Validation:** Side-by-side visual comparison with R2K charts

#### 1.3 Validation Test Harness
**Owner:** Code
```
Build automated testing framework for R2K compatibility:
- Read R2K exported CSV files
- Run equivalent Response-YOLO analysis
- Compare results with configurable tolerances (default 2%)
- Generate detailed discrepancy reports
- CI/CD integration for regression testing
```

**Files to create:**
- `tests/validation/test_r2k_parity.py` - Main test suite
- `tests/validation/comparator.py` - Result comparison utilities
- `tests/validation/conftest.py` - Pytest fixtures for R2K data loading

**Success Criteria:**
- All 5+ M-φ validation cases pass with <2% error in key metrics
- Automated reports identify any discrepancies with context

### Phase 2: Shear Analysis Completion (Week 3-4)

**Goal:** V-γ analysis fully functional with R2K parity

**Prerequisites:**
- R2K shear analysis workflow documented
- V-γ validation cases created

**Tasks:**

#### 2.1 V-γ Solver Integration
**Owner:** Code
```
Complete shear analysis implementation in analysis/shear_analysis.py:
- Use existing integrate_forces_shear() for section integration
- Newton-Raphson on ε₀ to enforce N=0 at each (M, γxy₀) state
- Increment γxy₀ from 0 → failure in adaptive steps
- Detect failure modes: compression crushing, stirrup yield, crack slip
- Return V-γ curve with annotated failure point
```

**Files to modify:**
- `analysis/shear_analysis.py` - Complete solver implementation
- `analysis/failure_criteria.py` - New module for failure detection

**Validation:** Numerical stability and convergence on simple cases

#### 2.2 Shear Stress Distribution
**Owner:** Code
```
Integrate Longitudinal Stiffness Method for shear stress visualization:
- Compute shear flow distribution at key load points
- Generate τ(z) diagrams
- Overlay stirrup stress on concrete shear stress
- Match R2K presentation format
```

**Files to modify:**
- `analysis/longitudinal_stiffness.py` - Enhance output data
- `visualization/plots.py` - Add shear stress plot functions

#### 2.3 R2K Output Format for Shear
**Owner:** Code
```
Extend output module to handle shear analysis results:
- V-γ curve data export
- Shear capacity summary (V_n, failure mode)
- Shear stress distribution tables
- Match R2K CSV/report formats exactly
```

**Files to modify:**
- `io/output.py` - Add shear-specific formatting
- Update CLI for shear analysis mode

**Success Criteria:**
- V-γ validation cases pass <5% error threshold
- Shear stress distributions visually match R2K
- Correct failure mode identification

### Phase 3: Coupled M-V Analysis (Week 5-6)

**Goal:** Simultaneous moment-shear analysis with interaction diagrams

**Prerequisites:**
- R2K coupled analysis workflow documented
- Understanding of M-V interaction surface

**Tasks:**

#### 3.1 3-DOF Equilibrium Solver
**Owner:** Code
```
Implement coupled M-V sectional analysis (Bentz Ch 7):
- Newton-Raphson on (ε₀, φ, γxy₀) for given (N, M, V)
- Use 3×3 stiffness matrix from integrate_stiffness_3x3()
- Convergence enhancements: arc-length method, line search
- Handle near-singular stiffness at failure
```

**Files to create:**
- `analysis/coupled_analysis.py` - 3-DOF solver
- `analysis/convergence.py` - Advanced solver utilities

**Validation:** Hand calculations for simple load cases

#### 3.2 Proportional Loading Paths
**Owner:** Code
```
Implement load-controlled analysis with M/V ratios:
- Increment along specified M/V path
- Track full response (M-φ AND V-γ simultaneously)
- Detect load reversal points on softening branch
- Generate combined load-deformation output
```

**Files to modify:**
- `analysis/coupled_analysis.py` - Add proportional loading

#### 3.3 Interaction Diagram Generation
**Owner:** Code
```
Build M-V interaction surface calculator:
- Sweep through M/V ratios from 0 (pure shear) to ∞ (pure flexure)
- Compute capacity at each ratio
- Generate 2D interaction curve
- Optional: 3D surface with axial load variation
```

**Files to create:**
- `analysis/interaction.py` - Interaction diagram calculator
- `visualization/interaction_plots.py` - Interaction curve plotting

**Success Criteria:**
- Coupled analysis runs without divergence
- Interaction diagrams match R2K shape and capacities
- Correctly handles moment-shear coupling effects

### Phase 4: Streamlit Interface (Week 7-8)

**Goal:** Web-based UI for section definition and analysis

**Tasks:**

#### 4.1 Section Definition Interface
**Owner:** Code
```
Build Streamlit app for interactive section creation:
- Form inputs for geometry (width, height, cover, etc.)
- Reinforcement layout tool (bar selection, spacing)
- Material library with dropdown selection
- Live cross-section preview (matplotlib figure)
- Input validation with helpful error messages
```

**Files to create:**
- `streamlit_app/app.py` - Main application entry point
- `streamlit_app/pages/section_builder.py` - Section definition page
- `streamlit_app/components/section_preview.py` - Live drawing widget
- `streamlit_app/utils/materials.py` - Material library interface

**UI Requirements:**
- Match R2K workflow: geometry → materials → reinforcement → review
- Intuitive for engineers unfamiliar with Python
- Mobile-responsive (basic tablet support)

#### 4.2 Analysis Dashboard
**Owner:** Code
```
Create analysis execution and results visualization interface:
- Analysis type selector (M-φ, V-γ, M-V interaction)
- Load parameter inputs (applied loads, boundary conditions)
- Progress indicator for long-running analyses
- Results tabs: charts, tables, summary statistics
- Export buttons (CSV, PDF report, PNG charts)
```

**Files to create:**
- `streamlit_app/pages/analysis.py` - Analysis configuration page
- `streamlit_app/pages/results.py` - Results dashboard
- `streamlit_app/components/charts.py` - Interactive Plotly charts

**Features:**
- One-click re-run with modified inputs
- Side-by-side comparison of multiple analyses
- Download complete analysis report as PDF

#### 4.3 Project Management
**Owner:** Code
```
Add session state management for saving/loading work:
- Save section definitions to JSON
- Load previous analyses
- Session history (recently analyzed sections)
- Optional: User authentication for multi-user deployment
```

**Files to modify:**
- `streamlit_app/utils/session.py` - State management
- `streamlit_app/utils/storage.py` - File I/O utilities

**Success Criteria:**
- Non-technical user completes M-φ analysis in <5 minutes
- Results match CLI output exactly
- App deployable to Streamlit Cloud free tier

### Phase 5: MCP Server & Claude Integration (Week 9)

**Goal:** Natural language interface via Claude

**Tasks:**

#### 5.1 MCP Server Implementation
**Owner:** Code
```
Build MCP server exposing Response-YOLO functionality:
- Tools for section creation from natural language descriptions
- Material assignment with common engineering terminology
- Analysis execution with conversational parameters
- Result querying and interpretation
- Chart generation (return as base64 images)
```

**Files to create:**
- `mcp_server/server.py` - MCP server implementation
- `mcp_server/tools/section.py` - Section creation tools
- `mcp_server/tools/analysis.py` - Analysis execution tools
- `mcp_server/tools/visualization.py` - Chart generation tools
- `mcp_server/prompts.py` - System prompts for context

**Tool Examples:**
```
create_section(description: str) -> SectionID
  "12x24 inch beam with 4 #8 bars, 2 inch cover"
  
assign_materials(section_id: str, fc_ksi: float, fy_ksi: float)
  
run_moment_curvature(section_id: str) -> AnalysisResult

compare_sections(section_ids: list[str], analysis_type: str) -> Comparison
```

#### 5.2 Conversational Workflows
**Owner:** Jamie + Claude (testing)
```
Design and test conversational analysis patterns:
- Guided section definition through Q&A
- Iterative design exploration ("what if #9 bars?")
- Explanation of results in plain English
- Failure mode interpretation and recommendations
```

**Deliverables:**
- `docs/mcp_usage_examples.md` - Example conversations
- `mcp_server/README.md` - Setup and usage guide

#### 5.3 Integration with Plotting
**Owner:** Code
```
Enable Claude to generate and display analysis visualizations:
- Call plotting functions via MCP tools
- Return charts as artifacts (base64 encoded images)
- Annotate charts with conversational explanations
- Support comparative visualizations
```

**Success Criteria:**
- Claude can complete full analysis workflow via MCP
- Charts render correctly in Claude interface
- Natural iteration without exposing JSON/CLI complexity

### Phase 6: Deployment & Documentation (Week 10)

**Goal:** Production-ready deployment and comprehensive documentation

**Tasks:**

#### 6.1 Streamlit Deployment
**Owner:** Jamie with Code assistance
```
Deploy web app to Streamlit Cloud:
- Configure secrets management (if needed)
- Set up custom domain (optional)
- Performance optimization (caching, lazy loading)
- Usage analytics integration (optional)
```

**Deliverables:**
- Live web app URL
- Deployment documentation

#### 6.2 MCP Server Deployment
**Owner:** Code
```
Package MCP server for distribution:
- Docker container with all dependencies
- Installation script for local deployment
- Configuration guide for Claude Desktop integration
- Environment variable documentation
```

**Files to create:**
- `Dockerfile` - MCP server container
- `docker-compose.yml` - Local deployment stack
- `mcp_server/INSTALL.md` - Setup instructions

#### 6.3 User Documentation
**Owner:** Jamie with Code assistance
```
Create comprehensive user documentation:
- Getting started guide (CLI, Streamlit, MCP)
- Input file format reference
- Analysis type descriptions with examples
- Output interpretation guide
- Troubleshooting common issues
```

**Deliverables:**
- `docs/user_guide/` - Complete documentation
- Tutorial videos (optional)
- Example analysis repository

#### 6.4 Developer Documentation
**Owner:** Code
```
Document codebase for contributors:
- Architecture overview and design decisions
- Module API reference (docstrings)
- Testing guide
- Contribution guidelines
- Bentz thesis cross-reference (which sections implemented where)
```

**Files to create:**
- `docs/developer_guide/ARCHITECTURE.md`
- `docs/developer_guide/API_REFERENCE.md`
- `docs/developer_guide/CONTRIBUTING.md`
- `CHANGELOG.md` - Version history

## Validation Strategy

### Differential Testing Against R2K

**Philosophy:** Since Response-YOLO is an R2K clone, the primary validation is matching R2K outputs, not comparing to experimental data or hand calculations.

**Test Pyramid:**

#### Level 1: Unit Tests (Existing)
- Material model behavior
- Section geometry calculations
- Numerical solver convergence
- **Status:** 73 tests passing

#### Level 2: R2K Parity Tests (To Be Built)
**Structure:**
```
tests/validation/
├── test_moment_curvature_parity.py
├── test_shear_parity.py
├── test_coupled_parity.py
├── baseline_data/
│   ├── case_001_simple_beam/
│   │   ├── r2k_input.json
│   │   ├── r2k_output.csv
│   │   └── metadata.yaml
│   ├── case_002_tee_section/
│   └── ...
└── comparator.py
```

**Test Case Coverage:**
- Simple cases: 5-10 basic geometries and loading
- Complex cases: 5-10 advanced features (T-sections, prestressing, high shear)
- Edge cases: 3-5 unusual configurations (min reinforcement, extreme loads)

**Comparison Metrics:**
- Ultimate capacity (M_n, V_n): ±2% tolerance
- Load-deformation curves: ±5% RMS error
- Failure modes: exact match
- Strain/stress profiles: ±10% at key points

**Automated Reporting:**
```python
# Example test structure
def test_case_001_simple_beam():
    """Rectangular section, Grade 60 steel, 4 ksi concrete."""
    r2k_results = load_r2k_baseline('case_001')
    yolo_results = run_response_yolo('case_001')
    
    comparison = compare_results(r2k_results, yolo_results)
    
    assert comparison.ultimate_moment_error < 0.02
    assert comparison.curve_rmse < 0.05
    assert comparison.failure_mode_matches
    
    # Generate detailed report
    comparison.save_report('validation_reports/case_001.html')
```

#### Level 3: Integration Tests
- Full workflow testing (input → analysis → output)
- Multi-analysis workflows (run M-φ, then V-γ on same section)
- Error handling and edge case behavior

### Acceptance Criteria for Each Phase

**Phase 1 (M-φ):**
- ✅ All M-φ validation cases pass with <2% capacity error
- ✅ Plots visually indistinguishable from R2K
- ✅ CSV exports have identical schema

**Phase 2 (Shear):**
- ✅ V-γ validation cases pass with <5% capacity error
- ✅ Failure modes correctly identified
- ✅ Shear stress distributions match R2K patterns

**Phase 3 (Coupled):**
- ✅ Interaction diagrams match R2K within 5%
- ✅ Combined loading analysis converges reliably
- ✅ Handles full range of M/V ratios

**Phase 4 (Streamlit):**
- ✅ UI workflow mirrors R2K user experience
- ✅ Results identical to CLI for same inputs
- ✅ Responsive design works on tablets

**Phase 5 (MCP):**
- ✅ Claude can complete analysis via conversation
- ✅ Natural language section descriptions parsed correctly
- ✅ Charts render in Claude interface

## Interface Architecture

### 1. CLI (Core Layer)
**Current:** Basic functionality
**Target:** Full-featured command-line interface

```bash
# Basic usage
response-yolo analyze section.json --analysis moment-curvature

# Advanced options
response-yolo analyze section.json \
  --analysis coupled \
  --moment 500 \
  --shear 100 \
  --output-format r2k \
  --plot \
  --export-report report.pdf
```

**Features:**
- JSON/R2T input file support
- Multiple output formats (CSV, JSON, R2K-compatible)
- Optional visualization generation
- Batch processing mode
- Verbose/debug logging

### 2. Streamlit Web App
**Technology:** Streamlit + Plotly
**Deployment:** Streamlit Cloud (free tier)

**Architecture:**
```
streamlit_app/
├── app.py                    # Entry point, routing
├── pages/
│   ├── home.py              # Welcome, recent projects
│   ├── section_builder.py   # Interactive section definition
│   ├── analysis.py          # Analysis configuration
│   └── results.py           # Results dashboard
├── components/
│   ├── section_preview.py   # Live cross-section drawing
│   ├── material_selector.py # Material library UI
│   ├── charts.py            # Interactive Plotly visualizations
│   └── export.py            # PDF/CSV export widgets
└── utils/
    ├── session.py           # State management
    ├── storage.py           # File I/O
    └── validation.py        # Input validation
```

**User Flow:**
1. Land on home page → "New Analysis" or "Load Project"
2. Section Builder → Define geometry, materials, reinforcement
3. Analysis Config → Select analysis type, set parameters
4. Run → Progress indicator
5. Results → Interactive charts, tables, export options

### 3. MCP Server (Claude Integration)
**Technology:** MCP protocol
**Deployment:** Docker container (local or cloud)

**Tool Schema:**
```python
# Section Creation
{
  "name": "create_section",
  "description": "Create a reinforced concrete section from natural language",
  "parameters": {
    "description": "string",  # "12x24 inch beam with 4 #8 bars"
    "section_type": "rectangular | tee | circular"
  }
}

# Analysis Execution
{
  "name": "run_analysis",
  "description": "Execute sectional analysis",
  "parameters": {
    "section_id": "string",
    "analysis_type": "moment_curvature | shear | coupled",
    "loads": "object"  # Flexible load specification
  }
}

# Visualization
{
  "name": "generate_chart",
  "description": "Create analysis visualization",
  "parameters": {
    "result_id": "string",
    "chart_type": "m_phi_curve | strain_profile | interaction_diagram",
    "annotations": "array"  # Optional highlights/callouts
  }
}

# Comparison
{
  "name": "compare_designs",
  "description": "Compare multiple section designs",
  "parameters": {
    "section_ids": "array",
    "metric": "capacity | ductility | efficiency"
  }
}
```

**Conversational Patterns:**

*Example 1: Guided Design*
```
User: I need to design a beam for a parking garage
Claude: [asks about span, loading, constraints]
User: 30 foot span, 500 lb/ft live load
Claude: [calculates trial section, creates via MCP]
Claude: I've created a 14x28" beam with 6 #9 bars. 
       Running moment-curvature analysis...
       [generates M-φ curve]
       This provides 650 kip-ft capacity with good ductility.
       Want to try a deeper section for less reinforcement?
```

*Example 2: Iterative Refinement*
```
User: Show me the beam we analyzed yesterday
Claude: [searches past conversations, retrieves section_id]
       Here's the 12x24" beam with 4 #8 bars.
       [displays section drawing]
User: What if I use #9 bars instead?
Claude: [modifies section, re-runs analysis]
       Capacity increases 15% to 380 kip-ft.
       [shows comparative M-φ curves]
       Yield curvature is similar, but ultimate is higher.
```

## Technology Stack

### Core Engine
- **Language:** Python 3.11+
- **Numerical:** NumPy, SciPy
- **Testing:** pytest, pytest-cov
- **Documentation:** Sphinx (autodoc from docstrings)

### Visualization
- **Static plots:** matplotlib
- **Interactive charts:** Plotly
- **Section drawings:** matplotlib patches, custom rendering

### CLI
- **Framework:** Click or Typer
- **Progress bars:** tqdm
- **Terminal output:** Rich (colored, formatted output)

### Streamlit Web App
- **Framework:** Streamlit 1.30+
- **Charts:** Plotly (interactive)
- **PDF generation:** ReportLab or matplotlib → PDF
- **Deployment:** Streamlit Cloud

### MCP Server
- **Framework:** MCP SDK (official Anthropic library)
- **API:** FastAPI (if HTTP gateway needed)
- **Containerization:** Docker
- **Deployment:** Docker Compose (local) or cloud container service

### Development Tools
- **Version control:** Git + GitHub
- **CI/CD:** GitHub Actions
- **Code formatting:** black, isort
- **Linting:** ruff
- **Type checking:** mypy (gradual adoption)

## Success Metrics

### Technical Metrics
- **Validation pass rate:** >95% of R2K test cases within tolerance
- **Test coverage:** >80% code coverage
- **Performance:** M-φ analysis <5 seconds for typical section
- **Convergence rate:** >98% of analyses converge without manual intervention

### Usability Metrics (Streamlit)
- **Time to first analysis:** <5 minutes for new user
- **Task completion rate:** >90% of users complete full workflow
- **Error rate:** <5% of analyses fail due to invalid inputs
- **User satisfaction:** Qualitative feedback (survey optional)

### Adoption Metrics
- **Deployment:** Streamlit app live and accessible
- **MCP integration:** Successfully integrated with Claude Desktop
- **Documentation completeness:** All features documented with examples

## Risk Management

### Technical Risks

**Risk:** Numerical convergence failures in coupled analysis
- **Mitigation:** Implement robust fallback strategies (arc-length method, load relaxation)
- **Contingency:** Comprehensive logging to diagnose failures, user guidance on input adjustments

**Risk:** R2K output format changes in future versions
- **Mitigation:** Version-lock validation test cases, document R2K version tested against
- **Contingency:** Maintain backward compatibility, update parsers as needed

**Risk:** Performance bottlenecks in web app
- **Mitigation:** Profile early, cache expensive computations, use Streamlit @st.cache
- **Contingency:** Async analysis execution, progress streaming

### Scope Risks

**Risk:** Feature creep beyond R2K clone scope
- **Mitigation:** Strict adherence to R2K feature catalog, defer enhancements to post-v1.0
- **Contingency:** Maintain "future features" backlog, prioritize ruthlessly

**Risk:** Underestimating R2K reverse engineering effort
- **Mitigation:** Allocate buffer time for discovery phase, start early
- **Contingency:** Prioritize most-used features, defer edge cases

### Resource Risks

**Risk:** Code's context limitations on large refactors
- **Mitigation:** Break tasks into <3 file edits, provide clear specifications
- **Contingency:** Manual coding for complex multi-module changes

**Risk:** Jamie's time constraints
- **Mitigation:** Front-load manual tasks (R2K documentation), automate where possible
- **Contingency:** Extend timeline, reduce scope to MVP if needed

## Next Actions

### Immediate (This Week)
1. **Jamie:** Install R2K, begin feature catalog documentation
2. **Jamie:** Run 3-5 example analyses, export all output formats
3. **Jamie:** Document M-φ workflow with screenshots
4. **Jamie + Claude:** Create output format specification from R2K samples

### Short-term (Next 2 Weeks)
1. **Code:** Implement R2K-compatible CSV export for M-φ
2. **Code:** Build plotting module matching R2K charts
3. **Code:** Create validation test harness
4. **Jamie:** Expand validation case library to 10+ cases

### Medium-term (Month 2)
1. **Code:** Complete shear analysis integration
2. **Code:** Begin Streamlit interface development
3. **Jamie:** User testing of Streamlit prototype

### Long-term (Month 3)
1. **Code:** Coupled analysis implementation
2. **Code:** MCP server development
3. **Jamie:** Documentation and deployment

## Appendix: Code Collaboration Patterns

### Effective Prompting for Code

**✅ Good Prompt Structure:**
```
Task: [One clear objective]

Context:
- Current state: [What exists now]
- Dependencies: [What this relies on]
- Constraints: [What must be preserved]

Specification:
- Input: [Data structures, formats]
- Output: [Expected results, formats]
- Validation: [How to test correctness]

Reference:
- Implementation guide: [Link to doc/thesis section]
- Example: [Paste relevant example if short]
```

**❌ Avoid:**
- Vague objectives ("improve the analysis")
- Multi-step tasks without prioritization
- Missing validation criteria
- Assuming Code remembers prior sessions

### Session Planning

**Optimal session scope:**
- 1-3 related files modified
- Clear acceptance test
- ~200 lines of new code maximum

**Break these into multiple sessions:**
- Large refactors touching 5+ files
- Algorithm redesign + UI changes
- Anything requiring extensive domain knowledge lookups

### When to Intervene Manually

**Code is excellent for:**
- Implementing well-specified algorithms
- Generating boilerplate (tests, config files)
- Refactoring within single modules
- Creating visualizations from clear examples

**Jamie should handle:**
- R2K reverse engineering (requires human judgment)
- Architecture decisions (Code can advise, not decide)
- Multi-module design changes (Code loses context)
- Final validation testing (human interpretation needed)

---

**Document Version:** 1.0  
**Last Updated:** February 2025  
**Next Review:** After Phase 1 completion
