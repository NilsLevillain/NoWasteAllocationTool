# techContext.md
# Technical Context: Technologies and Environment
## Core Technologies
      
### Backend
      - **Python 3.10+**: Primary programming language
      - **Flask 2.3.x**: Web framework for serving the application
      - **PuLP 2.7.x**: Linear programming library
      - **NumPy/Pandas**: Data manipulation and analysis
      - **openpyxl**: Excel file generation
      - **SQLAlchemy**: ORM for data persistence
      - **Redis**: Caching for optimization results
      
### Frontend
      - **HTML5/CSS3**: Markup and styling
      - **JavaScript (ES6+)**: Client-side scripting (ES6+)
      - **Highcharts**: Data visualization library
      - **Bootstrap 5**: UI framework
      - **jQuery**: DOM manipulation (minimized usage, primarily for Bootstrap/Highcharts if applicable)
      - **No dedicated table library**: Custom table rendering
      
## Development Environment
      - **Version Control**: Git with GitHub
      - **CI/CD**: GitHub Actions
      - **Containerization**: Docker
      - **IDE**: VS Code with Python and Flask extensions
      - **Testing**: unittest (for backend utilities), pytest, Jest
      - **Code Quality**: flake8, ESLint, Black (for Python), Prettier (for Frontend)
      
## Technical Constraints
      1. **Performance Requirements**:
         - Must solve problems with up to 10,000 products and 20 channels within 5 minutes
         - UI must remain responsive during optimization
         - Must support up to 50 concurrent users
      2. **Security Requirements**:
         - Authentication via L\Oréal SSO
         - Role-based access control
         - Data encryption at rest and in transit
         - Regular security audits
      3. **Compatibility Requirements**:
         - Must work with Chrome, Edge, and Firefox (latest versions)
         - Excel exports must be compatible with Excel 2019+
         - Must integrate with SAP via standardized file formats
      
## Dependencies and Configuration
      - **Configuration Management**: Environment variables with python-dotenv
      - **Package Management**: pip/pip-tools (via requirements.txt)
      - **Deployment**: GCP via docker
      - **Monitoring**: Prometheus and Grafana
      - **Logging**: GCP services
