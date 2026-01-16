import requests, json, time, sys

query = r"""\item \textbf{Differential Geometry (Curvature).}
Let $(M,g)$ be a $2$-dimensional Riemannian manifold with Gaussian curvature $K$.
Show that if $K\equiv 0$ on a simply connected open set $U\subset M$,
then $(U,g)$ is locally isometric to an open subset of $(\mathbb{R}^2,\langle\cdot,\cdot\rangle)$.
Conclude that a flat torus is isometric to $\mathbb{R}^2/\Lambda$ for some lattice \Lambda\subset\mathbb{R}^2."""

payload = {'text_query': query, 'user_id': 1}
print('Sending request...')
start = time.time()
try:
    r = requests.post('http://localhost:8000/api/v1/solve', json=payload, timeout=120)
    duration = time.time() - start
    print(f'Status: {r.status_code}')
    print(f'Time: {duration:.2f}s')
    if r.status_code == 200:
        data = r.json()
        sol = data.get('solution', {})
        print('Steps:', len(sol.get('steps', [])))
        print('Visuals:', len(sol.get('visuals', [])))
        for i, v in enumerate(sol.get('visuals', [])):
            print(f'Visual {i}: Type={v.get("type")}, Label={v.get("label")}')
            points = v.get("data", {}).get("points", [])
            print(f'  Points count: {len(points)}')

        print('Final Answer length:', len(sol.get('final_answer', {}).get('answer_text', '')))
    else:
        print('Error:', r.text)
except Exception as e:
    print(f'Exception: {e}')
