import io
import json
import unittest
import urllib.error
from diagnostico_whatsapp import PHONE_ID, ACCOUNT_ID, diagnose


class OfficialPhoneDiagnosticTest(unittest.TestCase):
    def test_only_reads_real_number_and_does_not_claim_activation(self):
        calls=[]
        def sender(request,timeout):
            calls.append(request)
            self.assertNotIn('private-token',request.full_url)
            self.assertEqual(request.get_method(),'GET')
            self.assertIsNone(request.data)
            if request.full_url.endswith('fields=display_phone_number,verified_name'):
                data={'display_phone_number':'+55 54 3443-6405','verified_name':'Sais Blue - Willian'}
            elif 'fields=platform_type' in request.full_url:data={'platform_type':'CLOUD_API'}
            elif 'fields=is_on_biz_app' in request.full_url:data={'is_on_biz_app':True}
            elif 'fields=code_verification_status' in request.full_url:data={'code_verification_status':'VERIFIED'}
            elif '/phone_numbers' in request.full_url:data={'data':[{'id':PHONE_ID,'display_phone_number':'555434436405'}]}
            else:data={'data':[{'whatsapp_business_api_data':{'id':'1111043088389561'}}]}
            return io.BytesIO(json.dumps(data).encode())
        report=diagnose('private-token',sender)
        self.assertEqual(report['read_access'],'confirmed')
        self.assertTrue(report['phone_belongs_to_account'])
        self.assertTrue(report['is_on_biz_app'])
        self.assertFalse(report['whatsapp_activated'])
        self.assertNotIn('private-token',json.dumps(report))
        self.assertTrue(all('/'+PHONE_ID in r.full_url or '/'+ACCOUNT_ID in r.full_url for r in calls))

    def test_expired_token_has_conclusive_code_without_repeated_probes(self):
        calls=[]
        def sender(request,timeout):
            calls.append(request)
            raise urllib.error.HTTPError(request.full_url,401,'denied',{},io.BytesIO(b'{"error":{"code":190,"error_subcode":463,"message":"private-token"}}'))
        report=diagnose('private-token',sender)
        self.assertEqual(len(calls),1)
        self.assertEqual(report['phone_check']['code'],190)
        self.assertNotIn('private-token',json.dumps(report))
        self.assertTrue(report['findings'][0].startswith('TOKEN_INVALIDO'))

    def test_unknown_optional_field_is_not_interpreted_as_no_coexistence(self):
        def sender(request,timeout):
            if 'display_phone_number,verified_name' in request.full_url:
                return io.BytesIO(b'{"display_phone_number":"555434436405"}')
            raise urllib.error.HTTPError(request.full_url,400,'unknown field',{},io.BytesIO(b'{"error":{"code":100}}'))
        report=diagnose('private-token',sender)
        self.assertEqual(report['is_on_biz_app'],'unknown')
        self.assertEqual(report['read_access'],'confirmed')
        self.assertFalse(report['whatsapp_activated'])
