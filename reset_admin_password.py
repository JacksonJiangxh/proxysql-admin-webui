#!/usr/bin/env python3
"""Reset admin user password for testing."""
import aiosqlite
from app.utils.security import hash_password
import asyncio

async def reset_password():
    # Use the test database path
    db_path = 'data/app_test.db'
    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row
    try:
        # Check if admin user exists
        cursor = await db.execute('SELECT * FROM users WHERE username = ?', ('admin',))
        result = await cursor.fetchone()
        if result:
            print('Found admin user:', dict(result))
            # Update password
            new_hash = hash_password('admin123')
            await db.execute('UPDATE users SET password_hash = ? WHERE username = ?', (new_hash, 'admin'))
            await db.commit()
            print('Password updated successfully')
        else:
            print('Admin user not found, creating...')
            new_hash = hash_password('admin123')
            await db.execute(
                'INSERT INTO users (username, password_hash, role, email) VALUES (?, ?, ?, ?)',
                ('admin', new_hash, 'admin', 'admin@localhost')
            )
            await db.commit()
            print('Admin user created successfully')
    finally:
        await db.close()

if __name__ == '__main__':
    asyncio.run(reset_password())
