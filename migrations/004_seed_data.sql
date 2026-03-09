INSERT INTO candidates (username, display_name) VALUES
('charlles.evangelista', 'Charlles Evangelista'),
('delegadasheila', 'Delegada Sheila')
ON CONFLICT (username) DO NOTHING;
