"""Run the real matcher on fictional inputs. No discovery or applications."""
from pathlib import Path
import json, sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from job_agent.matching import match_job
from job_agent.eligibility import classify_pakistan_eligibility

def run():
    profile=json.loads(Path(__file__).with_name('sample_profile.json').read_text())
    description='Remote worldwide; work from anywhere. Requirements: 3 years technical support, Python, REST API and troubleshooting. SQL experience required.'
    result=match_job('Technical Support Engineer',description,profile)
    print('OFFLINE DEMO / fictional profile and job')
    print('ROLE     Technical Support Engineer')
    print('PROFILE  5 years technical support')
    print('')
    print(f'MATCH    {result.score:.0f} / 100')
    print(f'Title {result.title_score:.0f}   Skills {result.skill_score:.0f}   Experience {result.experience_score:.0f}')
    print('MATCHED  '+', '.join(result.matched_skills))
    print('MISSING  '+', '.join(result.missing_skills))
    print('')
    for label,text in [('Worldwide remote',description),('US residency required','Remote role. Must reside in the United States.')]:
        status,reason=classify_pakistan_eligibility(text)
        print(f'{label} -> {status}')
        print('  '+reason)
    print('')
    print('Rule-based score. Review gaps and geography before applying.')
    print('No live discovery. No applications submitted.')

if __name__=='__main__': run()
