                <!-- ARCHIVADOR AISLADO POR USUARIO -->
                <div class="panel">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
                        <h3 style="margin: 0; font-size: 1rem; color: var(--primary);">📂 Archivador (Sandbox Personal)</h3>
                        <span style="font-size: 0.75rem; color: var(--text-muted);">/<?php echo e($currentPath); ?></span>
                    </div>

                    <?php if ($flash): ?>
                        <div class="toast-error" style="background: rgba(16,185,129,0.2); border-color: var(--accent-green); color: #6ee7b7;"><?php echo e($flash['message']); ?></div>
                    <?php endif; ?>

                    <div style="display: flex; flex-direction: column; gap: 8px; margin-bottom: 12px;">
                        <?php if ($currentPath !== ''): ?>
                            <a href="?path=<?php echo e(dirname(normalize_relative_path($currentPath))); ?>" class="outline" style="padding: 6px; text-align: center; text-decoration: none; font-size: 0.8rem; border-radius: 6px;">⬅️ Subir Nivel</a>
                        <?php endif; ?>
                        <form method="post" action="?action=create_folder&path=<?php echo e($currentPath); ?>" style="display: flex; gap: 6px;">
                            <input type="text" name="name" placeholder="Nueva Carpeta" required style="padding: 6px; font-size: 0.8rem;">
                            <button type="submit" style="padding: 6px 10px; font-size: 0.8rem;">📁</button>
                        </form>
                        <form method="post" action="?action=create_file&path=<?php echo e($currentPath); ?>" style="display: flex; gap: 6px;">
                            <input type="text" name="name" placeholder="Nuevo Archivo.php" required style="padding: 6px; font-size: 0.8rem;">
                            <button type="submit" style="padding: 6px 10px; font-size: 0.8rem;">📄</button>
                        </form>
                    </div>

                    <table class="tabla">
                        <thead><tr><th>Nombre</th><th>Tamaño</th><th>Acciones</th></tr></thead>
                        <tbody>
                            <?php
                            $dirPath = safe_path($currentPath);
                            $items = scandir($dirPath) ?: [];
                            foreach ($items as $item) {
                                if ($item === '.' || $item === '..') continue;
                                $itemPath = $dirPath . DIRECTORY_SEPARATOR . $item;
                                $rel = relative_path($itemPath);
                                $isDir = is_dir($itemPath);
                            ?>
                            <tr>
                                <td>
                                    <?php echo file_icon($item, $isDir); ?>
                                    <?php if ($isDir): ?>
                                        <a href="?path=<?php echo urlencode($rel); ?>" style="color: var(--primary); font-weight: bold; text-decoration: none;"><?php echo e($item); ?></a>
                                    <?php else: ?>
                                        <span><?php echo e($item); ?></span>
                                    <?php endif; ?>
                                </td>
                                <td><?php echo $isDir ? '-' : format_bytes(filesize($itemPath)); ?></td>
                                <td>
                                    <div style="display: flex; gap: 4px;">
                                        <?php if (!$isDir): ?>
                                            <a href="?action=download&path=<?php echo urlencode($rel); ?>" class="outline" style="padding: 2px 6px; font-size: 0.7rem; text-decoration: none;">⬇️</a>
                                        <?php endif; ?>
                                        <form method="post" action="?action=delete" onsubmit="return confirm('¿Borrar?');" style="margin:0;">
                                            <input type="hidden" name="target" value="<?php echo e($rel); ?>">
                                            <button type="submit" class="danger-outline" style="padding: 2px 6px; font-size: 0.7rem;">🗑️</button>
                                        </form>
                                    </div>
                                </td>
                            </tr>
                            <?php } ?>
                        </tbody>
                    </table>
                </div>
