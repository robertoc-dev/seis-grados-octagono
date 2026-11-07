# Seis Grados del Octágono

Reto diario de MMA: conecta a dos peleadores de UFC con una cadena de rivales en seis grados o menos.
Tiene dos modos: **Toda la historia** (todas las peleas de UFC desde 1993) y **Solo rankeados**
(campeones y top 15 actuales, más fácil).

## Cómo se actualiza solo

El workflow `.github/workflows/actualizar.yml` corre en GitHub Actions:

| Cuándo (hora de El Salvador) | Qué hace |
|---|---|
| Domingo 8:17 a.m. | Descarga las peleas del sábado y publica |
| Miércoles 8:17 p.m. | Revisa los rankings oficiales (salen los martes) y publica |
| Cada vez que subes cambios a `main` | Regenera y publica |
| Cuando quieras | Botón **Run workflow** en la pestaña Actions |

En cada corrida:
1. `scripts/update_rankings.py` lee ufc.com/rankings y actualiza `data/rankings.json`.
   Si la página falla o cambia de formato, deja los rankings anteriores y muestra un aviso.
2. `scripts/build_game_data.py` descarga las peleas del dataset público
   [Greco1899/scrape_ufc_stats](https://github.com/Greco1899/scrape_ufc_stats) (datos de UFCStats.com)
   y genera `web/data/game_data.json`. Si los datos vienen incompletos, el paso falla y el sitio no cambia.
3. Guarda los datos nuevos en el repositorio y publica la carpeta `web/` en GitHub Pages.

## Puesta en marcha (una sola vez)

1. Crea un repositorio nuevo en GitHub, por ejemplo `seis-grados-octagono`. Puede ser público o privado
   (GitHub Pages en repositorios privados requiere un plan de pago).
2. Sube todo el contenido de esta carpeta, incluida la carpeta oculta `.github`:
   ```bash
   git init
   git add .
   git commit -m "Primera versión"
   git branch -M main
   git remote add origin https://github.com/TU_USUARIO/seis-grados-octagono.git
   git push -u origin main
   ```
   Si usas la web de GitHub en vez de la terminal ("Add file → Upload files"), arrastra la carpeta completa:
   la carpeta `.github` a veces no se sube si está oculta en tu sistema.
3. En el repositorio ve a **Settings → Pages** y en **Source** elige **GitHub Actions**.
4. Ve a la pestaña **Actions**, abre **Actualizar datos y publicar** y pulsa **Run workflow**.
5. Al terminar (unos 2 minutos), el enlace del juego aparece en el resumen de la corrida:
   `https://TU_USUARIO.github.io/seis-grados-octagono/`

## Tareas manuales

- **Un nombre del ranking no coincide con la base.** El resumen de la corrida muestra
  "Sin coincidencia: …". Agrega el nombre en `aliases` dentro de `data/rankings.json`, con el nombre
  tal como aparece en UFCStats. Ejemplo: `"Mizuki Inoue": "Mizuki"`.
- **ufc.com bloquea la descarga de rankings.** Verás el aviso en Actions. Edita `data/rankings.json`
  a mano (la posición 0 de cada lista es el campeón, luego del #1 al #15) y súbelo: eso dispara una
  publicación nueva.
- **Probar en tu computadora:**
  ```bash
  pip install -r requirements.txt
  python scripts/update_rankings.py
  python scripts/build_game_data.py --rankings data/rankings.json --out web/data/game_data.json
  cd web && python -m http.server 8000     # abre http://localhost:8000
  ```
  El juego necesita un servidor: si abres `index.html` con doble clic, el navegador no deja cargar los datos.

## Notas

- GitHub desactiva los workflows programados de repositorios públicos sin actividad durante 60 días.
  Como cada actualización guarda un commit, eso no debería pasar mientras haya carteleras nuevas.
- Los datos de peleas vienen de UFCStats.com a través de un proyecto de terceros. Antes de promocionar
  el juego, revisa sus condiciones de uso, y no uses el logo ni la marca UFC en el nombre del sitio.
