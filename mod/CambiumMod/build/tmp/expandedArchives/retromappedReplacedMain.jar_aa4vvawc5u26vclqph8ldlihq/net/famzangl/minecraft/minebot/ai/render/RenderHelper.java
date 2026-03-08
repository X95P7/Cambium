/*******************************************************************************
 * This file is part of Minebot.
 *
 * Minebot is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * Minebot is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with Minebot.  If not, see <http://www.gnu.org/licenses/>.
 *******************************************************************************/
package net.famzangl.minecraft.minebot.ai.render;

import net.famzangl.minecraft.minebot.ai.AIHelper;
import net.minecraft.client.renderer.GlStateManager;
import net.minecraft.client.renderer.Tessellator;
import net.minecraft.client.renderer.WorldRenderer;
import net.minecraft.client.renderer.vertex.VertexFormat;
import net.minecraft.client.renderer.vertex.VertexFormatElement;
import net.minecraft.entity.Entity;
import net.minecraft.util.BlockPos;
import net.minecraftforge.fml.common.gameevent.TickEvent.RenderTickEvent;

import org.lwjgl.opengl.GL11;

/**
 * Helps rendering markers.
 * 
 * @author michael
 * 
 */
public class RenderHelper {

	private static final double MAX = 1.05;
	private static final double MIN = -0.05;

    public static final VertexFormat VF = new VertexFormat();
    static {
        VF.func_181721_a(new VertexFormatElement(0, VertexFormatElement.EnumType.FLOAT, VertexFormatElement.EnumUsage.POSITION, 3));
        VF.func_181721_a(new VertexFormatElement(0, VertexFormatElement.EnumType.UBYTE, VertexFormatElement.EnumUsage.COLOR, 4));
    }

	public void renderStart(RenderTickEvent event, AIHelper helper) {
		final Entity player = helper.getMinecraft().func_175606_aa();
		final double x = player.field_70142_S
				+ (player.field_70165_t - player.field_70142_S) * event.renderTickTime;
		final double y = player.field_70137_T
				+ (player.field_70163_u - player.field_70137_T) * event.renderTickTime;
		final double z = player.field_70136_U
				+ (player.field_70161_v - player.field_70136_U) * event.renderTickTime;

		preRender();
        Tessellator tessellator = Tessellator.func_178181_a();
        WorldRenderer worldrenderer = tessellator.func_178180_c();
        worldrenderer.func_178969_c(-x, -y, -z);
        worldrenderer.func_181668_a(GL11.GL_QUADS, VF);
       // worldrenderer.markDirty();
	}

    private void preRender()
    {
        GlStateManager.func_179090_x();
        GlStateManager.func_179147_l();
        GlStateManager.func_179120_a(GL11.GL_DST_COLOR, GL11.GL_SRC_COLOR, 1, 0);

        GlStateManager.func_179131_c(1.0F, 1.0F, 1.0F, 1.0F);
        GlStateManager.func_179136_a(-3.0F, -3.0F);
        GlStateManager.func_179088_q();
        GlStateManager.func_179092_a(516, 0.1F);
        GlStateManager.func_179141_d();
        GlStateManager.func_179094_E();
    }

    private void postRender()
    {
        GlStateManager.func_179118_c();
        GlStateManager.func_179136_a(0.0F, 0.0F);
        GlStateManager.func_179113_r();
        GlStateManager.func_179141_d();
        GlStateManager.func_179132_a(true);
        GlStateManager.func_179121_F();
        GlStateManager.func_179084_k();
        GlStateManager.func_179098_w();
    }
	protected void renderEnd() {
		final Tessellator tessellator = Tessellator.func_178181_a();
        WorldRenderer worldrenderer = tessellator.func_178180_c();
		tessellator.func_78381_a();
		worldrenderer.func_178969_c(0.0D, 0.0D, 0.0D);
		postRender();
	}

	protected void renderMarker(BlockPos m, float r, float g, float b, float a) {
		final Tessellator tessellator = Tessellator.func_178181_a();
		WorldRenderer renderer = tessellator.func_178180_c();
		renderer.func_181666_a(r, g, b, a);
		renderMarkerP(renderer, m.func_177958_n(), m.func_177956_o(), m.func_177952_p());
	}

	private void renderMarkerP(WorldRenderer worldRenderer, int x, int y, int z) {
		worldRenderer.func_181662_b(x + MIN, y + MAX, z + MIN);
		worldRenderer.func_181662_b(x + MIN, y + MAX, z + MAX);
		worldRenderer.func_181662_b(x + MAX, y + MAX, z + MAX);
		worldRenderer.func_181662_b(x + MAX, y + MAX, z + MIN);

		worldRenderer.func_181662_b(x + MIN, y + MIN, z + MIN);
		worldRenderer.func_181662_b(x + MIN, y + MIN, z + MAX);
		worldRenderer.func_181662_b(x + MIN, y + MAX, z + MAX);
		worldRenderer.func_181662_b(x + MIN, y + MAX, z + MIN);

		worldRenderer.func_181662_b(x + MAX, y + MAX, z + MIN);
		worldRenderer.func_181662_b(x + MAX, y + MAX, z + MAX);
		worldRenderer.func_181662_b(x + MAX, y + MIN, z + MAX);
		worldRenderer.func_181662_b(x + MAX, y + MIN, z + MIN);

		worldRenderer.func_181662_b(x + MIN, y + MIN, z + MIN);
		worldRenderer.func_181662_b(x + MIN, y + MAX, z + MIN);
		worldRenderer.func_181662_b(x + MAX, y + MAX, z + MIN);
		worldRenderer.func_181662_b(x + MAX, y + MIN, z + MIN);

		worldRenderer.func_181662_b(x + MIN, y + MAX, z + MAX);
		worldRenderer.func_181662_b(x + MIN, y + MIN, z + MAX);
		worldRenderer.func_181662_b(x + MAX, y + MIN, z + MAX);
		worldRenderer.func_181662_b(x + MAX, y + MAX, z + MAX);

		worldRenderer.func_181662_b(x + MIN, y + MIN, z + MAX);
		worldRenderer.func_181662_b(x + MIN, y + MIN, z + MIN);
		worldRenderer.func_181662_b(x + MAX, y + MIN, z + MIN);
		worldRenderer.func_181662_b(x + MAX, y + MIN, z + MAX);
	}
}
