SUBJECTS = {
    'Mathematics': {
        'IGCSE': {
            'code': '0580/0980',
            'tiers': ['Core (Grades C-G)', 'Extended (Grades A*-E)'],
            'papers': {
                'Paper 1': {'tier': 'Core', 'duration': '1h 30min', 'marks': 80, 'weight': '35%', 'type': 'Non-calculator, short-answer structured', 'calculator': False},
                'Paper 2': {'tier': 'Extended', 'duration': '1h 30min', 'marks': 70, 'weight': '35%', 'type': 'Non-calculator, short-answer structured', 'calculator': False},
                'Paper 3': {'tier': 'Core', 'duration': '1h 30min', 'marks': 80, 'weight': '65%', 'type': 'Calculator allowed, structured questions', 'calculator': True},
                'Paper 4': {'tier': 'Extended', 'duration': '2h 30min', 'marks': 130, 'weight': '65%', 'type': 'Calculator allowed, structured questions', 'calculator': True},
            },
            'aos': {'AO1': 'Knowledge and understanding of mathematical techniques', 'AO2': 'Analyse, interpret and communicate mathematically'},
            'topics': ['Number', 'Algebra and graphs', 'Coordinate geometry', 'Geometry', 'Mensuration', 'Trigonometry', 'Transformations and vectors', 'Probability', 'Statistics'],
        },
        'IB': {
            'courses': ['Math AA SL', 'Math AA HL', 'Math AI SL', 'Math AI HL'],
            'papers_aa_sl': {
                'Paper 1': {'duration': '1h 30min', 'marks': 80, 'weight': '40%', 'calculator': False},
                'Paper 2': {'duration': '1h 30min', 'marks': 80, 'weight': '40%', 'calculator': True},
                'IA': {'weight': '20%', 'type': 'Mathematical Exploration (12-20 pages)'},
            },
            'topics': ['Number and algebra', 'Functions', 'Geometry and trigonometry', 'Statistics and probability', 'Calculus'],
        },
    },
    'Physics': {
        'IGCSE': {
            'code': '0625/0972',
            'papers': {
                'Paper 1/2': {'type': '40 MCQs', 'duration': '45min', 'marks': 40, 'weight': '30%'},
                'Paper 3/4': {'type': 'Short-answer & structured', 'duration': '1h 15min', 'marks': 80, 'weight': '50%'},
                'Paper 5/6': {'type': 'Practical/Alt to Practical', 'duration': '1h-1h15min', 'marks': 40, 'weight': '20%'},
            },
            'topics': ['Motion, forces and energy', 'Thermal physics', 'Waves', 'Electricity and magnetism', 'Nuclear physics', 'Space physics'],
        },
        'IB': {
            'papers_sl': {
                'Paper 1': {'type': '1A: MCQs + 1B: Data-based & short-answer', 'duration': '1h 30min', 'weight': '36%'},
                'Paper 2': {'type': 'Short-answer & extended response', 'duration': '1h 30min', 'weight': '44%'},
                'IA': {'weight': '20%', 'type': 'Scientific investigation (3000 words max)'},
            },
            'topics': ['Space, time and motion', 'Particulate nature of matter', 'Wave behaviour', 'Fields', 'Nuclear and quantum physics'],
        },
    },
    'Chemistry': {
        'IGCSE': {
            'code': '0620/0971',
            'papers': {
                'Paper 1/2': {'type': '40 MCQs', 'duration': '45min', 'marks': 40, 'weight': '30%'},
                'Paper 3/4': {'type': 'Short-answer & structured', 'duration': '1h 15min', 'marks': 80, 'weight': '50%'},
                'Paper 5/6': {'type': 'Practical/Alt to Practical', 'duration': '1h-1h15min', 'marks': 40, 'weight': '20%'},
            },
            'topics': ['States of matter', 'Atoms, elements and compounds', 'Stoichiometry', 'Electrochemistry', 'Chemical energetics', 'Chemical reactions', 'Acids, bases and salts', 'The Periodic Table', 'Metals', 'Chemistry of the environment', 'Organic chemistry'],
        },
        'IB': {
            'papers_sl': {
                'Paper 1': {'type': '1A: MCQs + 1B: Data-based & short-answer', 'duration': '1h 30min', 'weight': '36%'},
                'Paper 2': {'type': 'Short-answer & extended response', 'duration': '1h 30min', 'weight': '44%'},
                'IA': {'weight': '20%', 'type': 'Scientific investigation (3000 words max)'},
            },
            'topics': ['Models of the particulate nature of matter', 'Models of bonding and structure', 'Classification of matter', 'What drives chemical reactions?', 'How much, how fast and how far?', 'What are the mechanisms of chemical change?'],
        },
    },
    'Economics': {
        'IGCSE': {
            'code': '0455',
            'papers': {
                'Paper 1': {'type': 'Multiple Choice', 'duration': '45min', 'marks': 30, 'weight': '30%'},
                'Paper 2': {'type': 'Structured Questions', 'duration': '2h 15min', 'marks': 90, 'weight': '70%'},
            },
            'topics': ['The basic economic problem', 'The allocation of resources', 'Microeconomic decision makers', 'Government and the macroeconomy', 'Economic development', 'International trade and globalisation'],
        },
        'IB': {
            'papers_sl': {
                'Paper 1': {'type': 'Extended response', 'duration': '1h 15min', 'marks': 25, 'weight': '30%'},
                'Paper 2': {'type': 'Data response', 'duration': '1h 45min', 'marks': 40, 'weight': '40%'},
                'IA': {'type': 'Portfolio', 'weight': '30%'},
            },
            'topics': ['Introduction to economics', 'Microeconomics', 'Macroeconomics', 'The global economy'],
        },
    },
    'Computer Science': {
        'IGCSE': {
            'code': '0478/0984',
            'papers': {
                'Paper 1': {'type': 'Computer Systems', 'duration': '1h 45min', 'marks': 75, 'weight': '50%'},
                'Paper 2': {'type': 'Algorithms, Programming and Logic', 'duration': '1h 45min', 'marks': 75, 'weight': '50%'},
            },
            'topics': ['Data representation', 'Data transmission', 'Hardware', 'Software', 'The internet and its uses', 'Automated and emerging technologies', 'Algorithm design and problem-solving', 'Programming', 'Databases', 'Boolean logic'],
        },
        'IB': {
            'papers_sl': {
                'Paper 1': {'type': 'System fundamentals, Organization, Networks, Computational thinking', 'duration': '1h 30min', 'weight': '45%'},
                'Paper 2': {'type': 'Option (e.g. OOP)', 'duration': '1h', 'weight': '25%'},
                'IA': {'type': 'Solution', 'weight': '30%'},
            },
            'topics': ['System fundamentals', 'Computer organization', 'Networks', 'Computational thinking, problem-solving and programming', 'Option (OOP recommended)'],
        },
    },
    'ICT': {
        'IGCSE': {
            'code': '0417/0983',
            'papers': {
                'Paper 1': {'type': 'Theory', 'duration': '1h 30min', 'marks': 80, 'weight': '40%'},
                'Paper 2': {'type': 'Document Production, Data Manipulation and Presentations', 'duration': '2h 15min', 'marks': 80, 'weight': '30%'},
                'Paper 3': {'type': 'Data Analysis and Website Authoring', 'duration': '2h 15min', 'marks': 80, 'weight': '30%'},
            },
            'topics': ['Types and components of computer systems', 'Input and output devices', 'Storage devices and media', 'Networks and the effects of using them', 'The effects of using IT', 'ICT applications', 'The systems life cycle', 'Safety and security', 'Audience', 'Communication', 'File management', 'Images', 'Layout', 'Styles', 'Proofing', 'Graphs and charts', 'Document production', 'Data manipulation', 'Presentations', 'Data analysis', 'Website authoring'],
        },
        'IB': {
            'topics': [],
        }
    }
}
