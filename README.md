# UVTAB EMIS (Education Management Information System)

A comprehensive management system for Uganda Vocational and Technical Assessment Board (UVTAB) to handle candidate registration, assessment center management, and report generation.

## Features

- **Candidate Management**
  - Registration with unique ID generation (format: U/YY/M/OCC/R/XXX-CENTERCODE)
  - Photo upload and storage
  - Personal information tracking
  - Support for formal, informal, and modular registration categories

- **Assessment Center Management**
  - Center registration and management
  - Center code assignment
  - Center capacity tracking

- **Occupation & Level Management**
  - Multiple occupations support
  - Level tracking for formal/informal candidates
  - Module tracking for informal/modular candidates

- **Report Generation**
  - Registration list (albums) with candidate photos
  - Filterable by:
    - Assessment Center
    - Occupation
    - Registration Category
    - Level (for formal/informal)
    - Assessment Month/Year
  - Professional PDF output with:
    - UVTAB logo and header
    - Contact information
    - Candidate details in tabular format
    - Photo integration

## Technology Stack

- Python 3.12
- Django 5.2
- ReportLab for PDF generation
- SQLite database
- Tailwind CSS for styling

## Installation

1. Clone the repository:
```bash
git clone https://github.com/ClaireAgaba/uvtab_emis.git
cd uvtab_emis
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Run migrations:
```bash
python manage.py migrate
```

5. Create a superuser:
```bash
python manage.py createsuperuser
```

6. Run the development server:
```bash
python manage.py runserver
```

## Usage

1. Access the admin interface at `/admin` to manage:
   - Assessment Centers
   - Occupations
   - Levels
   - Modules
   - Candidates

2. Use the main interface to:
   - Register candidates
   - Generate registration lists
   - View and filter candidates
   - Manage assessment centers

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contact

Claire Agaba - [GitHub](https://github.com/ClaireAgaba)
