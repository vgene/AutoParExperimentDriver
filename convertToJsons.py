import json

with open("status.json", "r") as fd:
    obj = json.load(fd)
compatible_map_dict = {}
for bmark in obj:
    ei = obj[bmark]['Exp-ignorefn']
    if ei and 'compatible_map' in ei:
        compatible_map_dict[bmark] = ei['compatible_map']

sccs_dict = {}
for bmark in obj:
    ei = obj[bmark]['Exp-ignorefn']
    if not ei:
        continue
    if 'loop_order' not in ei:
        continue
    
    def getSCCs(exp):
        sccs = []
        loop_order = exp['loop_order']
        loops = exp['loops']
        for loop in loop_order:
            loi = loops[loop]['dependence_info']
            sccs.append([loi['largest_seq_scc'], loi['parallel_scc'], loi['sequential_scc']])
        return sccs
    sccs_dict[bmark+"-ignorefn"] = getSCCs(ei)
    es = obj[bmark]['Exp-slamp']
    if es:
        sccs_dict[bmark] = getSCCs(es)

coverage_dict = {}
for bmark in obj:
    coverages = []
    ei = obj[bmark]['Exp-ignorefn']
    if not ei:
        continue
    for loop in ei['loop_order']:
        coverages.append(ei['loops'][loop]['exec_coverage'])
    coverage_dict[bmark] = coverages

with open("coverage.json", "w") as fd:
    json.dump(coverage_dict, fd)

with open("sccs.json", "w") as fd:
    json.dump(sccs_dict, fd)

with open("compatible.json", "w") as fd:
    json.dump(compatible_map_dict, fd)
