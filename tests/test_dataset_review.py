import json
import tempfile
import unittest
from pathlib import Path
from fastapi.testclient import TestClient
from resolveguard.dashboard import create_dashboard
from resolveguard.dataset_review import calibration_report
from resolveguard.customer_review import fingerprint


class DatasetReviewTests(unittest.TestCase):
    def test_calibration_confusion_rates_and_latest_rejection(self):
        cases=[{'case_id':'CAL-001'},{'case_id':'CAL-002'}]
        reviews=[{'case_id':c['case_id'],'source_hash':fingerprint(c),'verdict':'APPROVED','expected':{'passed':i==0}}
                 for i,c in enumerate(cases)]
        result=calibration_report(cases,reviews,{'CAL-001':True,'CAL-002':True})
        self.assertEqual(result['true_positive_rate'],1)
        self.assertEqual(result['true_negative_rate'],0)
        self.assertEqual(result['false_passes'],1)
        reviews.append(dict(reviews[0],verdict='REJECTED'))
        result=calibration_report(cases,reviews,{'CAL-001':True,'CAL-002':'true'})
        self.assertEqual(result['human_model_pairs'],0)
        self.assertIsNone(result['agreement'])
        self.assertEqual(result['invalid_judge_case_ids'],['CAL-002'])

    def test_label_import_requires_human_attestation_and_exact_source(self):
        from tools.calibrate_human_review import import_reviews
        case={'case_id':'CAL-001'}
        row={'case_id':'CAL-001','source_hash':fingerprint(case),'human_mark':'PASS','reviewer':'human',
             'note':'Reviewed output against the supplied source','human_attestation':'false'}
        with self.assertRaises(ValueError):import_reviews([case],[row])
        row['human_attestation']='true'
        self.assertTrue(import_reviews([case],[row])[0]['expected']['passed'])
    def test_no_human_labels_means_no_calibration_score(self):
        cases=[{'case_id':'CAL-001','judge_passed':True}]
        self.assertIsNone(calibration_report(cases,[])['agreement'])
        self.assertEqual(calibration_report(cases,[])['status'],'PENDING_HUMAN_CALIBRATION')

    def test_human_disagreement_is_not_hidden(self):
        case={'case_id':'CAL-001','judge_passed':True}
        review={'case_id':'CAL-001','source_hash':fingerprint(case),'verdict':'APPROVED','expected':{'passed':False}}
        result=calibration_report([case],[review])
        self.assertEqual(result['agreement'],0)
        self.assertEqual(result['false_passes'],1)

    def test_source_hash_and_attestation_are_required(self):
        with tempfile.TemporaryDirectory() as temp,TestClient(create_dashboard(Path(temp),'local-test-admin-token-1234567890')) as client:
            headers={'Authorization':'Bearer local-test-admin-token-1234567890'}
            data=client.get('/api/reviewer/datasets',headers=headers).json()
            self.assertEqual(len(data['suites'][0]['items']),100)
            self.assertEqual(len(data['suites'][1]['items']),100)
            item=data['suites'][0]['items'][0]
            body={'suite':'original-100','case_id':item['case_id'],'source_hash':item['source_hash'],
                'verdict':'APPROVED','expected':item['source']['expected'],'note':'Checked source and fixture', 'human_attestation':False}
            self.assertEqual(client.post('/api/reviewer/datasets/review',headers=headers,json=body).status_code,422)
            body['human_attestation']=True;body['source_hash']='wrong-source'
            self.assertEqual(client.post('/api/reviewer/datasets/review',headers=headers,json=body).status_code,409)
