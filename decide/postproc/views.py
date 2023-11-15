from rest_framework.views import APIView
from rest_framework.response import Response


class PostProcView(APIView):

    def identity(self, options):
        out = []

        for opt in options:
            out.append({
                **opt,
                'postproc': opt['votes'],
            });

        out.sort(key=lambda x: -x['postproc'])
        return Response(out)
    
    def dhondt(self,options):
        res = []
        seats = int(self.request.data.get('seats',100))
        for x in options:
            opt_res = {
                'option': x['option'],
                'number': x['number'],
                'votes': x['votes'],
                'modified_votes': x['votes'],
                'dhondt': 0
            }
            res.append(opt_res)

        for i in range(0,seats):
            biggest_modified_votes = max(res,key=lambda x:x['modified_votes'])
            index = res.index(biggest_modified_votes)
            biggest_modified_votes['dhondt'] +=1
            biggest_modified_votes['modified_votes'] = biggest_modified_votes['votes']/(biggest_modified_votes['dhondt']+1)
            del res[index]
            res.append(biggest_modified_votes)
        for a in res:
            del a['modified_votes']
        res.sort(key=lambda x: -x['dhondt'])
        return Response(res)

    def webster(self, options):
        res = []
        seats = int(self.request.data.get('seats', 100))
        
        for x in options:
            opt_res = {
                'option': x['option'],
                'number': x['number'],
                'votes': x['votes'],
                'modified_votes': x['votes'],
                'webster': 0
            }
            res.append(opt_res)

        for i in range(0, seats):
            highest_quotient_party = max(res, key=lambda x: x['votes'] / (2 * x['webster'] + 1))
            index = res.index(highest_quotient_party)
            highest_quotient_party['webster'] += 1
            highest_quotient_party['modified_votes'] = highest_quotient_party['votes'] / (2 * highest_quotient_party['webster'] + 1)
            del res[index]
            res.append(highest_quotient_party)
        for a in res:
            del a['modified_votes']
        res.sort(key=lambda x: -x['webster'])
        return Response(res)

    def post(self, request):
        """
         * type: IDENTITY | EQUALITY | WEIGHT
         * options: [
            {
             option: str,
             number: int,
             votes: int,
             ...extraparams
            }
           ]
        """
        t = request.data.get('type')
        opts = request.data.get('options', [])
        if t == 'IDENTITY':
            return self.identity(opts)
        elif t == 'DHONDT':
            return self.dhondt(opts)
        elif t == 'WEBSTER':
            return self.webster(opts)

        return Response({})