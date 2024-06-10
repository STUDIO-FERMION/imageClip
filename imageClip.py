#coding:utf-8

import sys, codecs, jarray
from os import path, getenv
from math import ceil

from java.awt import (
    Toolkit, Robot, Insets, Rectangle, BorderLayout, Cursor, Color, Font, Frame,
    RenderingHints
    )
from java.awt.image import RescaleOp, BufferedImage
from java.awt.event import (
    MouseAdapter, MouseMotionAdapter, ActionListener, MouseListener, MouseMotionListener,
    KeyEvent, InputEvent, ActionListener, ActionEvent
    )
from java.awt.event.MouseEvent import BUTTON1, BUTTON3
from java.awt.event.InputEvent import BUTTON1_DOWN_MASK, BUTTON3_DOWN_MASK

from javax.swing import (
    JPanel, JFrame, JLabel, BorderFactory, JDialog, JPopupMenu, JMenu, JMenuItem, SwingUtilities,
    ToolTipManager, AbstractAction, KeyStroke, JComponent
    )
from java.lang import Runnable
from java.util.concurrent import TimeUnit
from java.awt.datatransfer import DataFlavor

FONT_JP = 'VL Gothic Regular'

clipboard = Toolkit.getDefaultToolkit().getSystemClipboard()
robot = Robot()
screenSize = Toolkit.getDefaultToolkit().getScreenSize()

class Guide(object):
    def __init__(self, minimum, maximum):
        self.size, self.min, self.max = (0.0, float(minimum), float(maximum))
        if 0.0 < self.min < self.max and (self.min*10).is_integer() and (self.max*10).is_integer():
            self.image = BufferedImage(1024, 256, BufferedImage.TYPE_4BYTE_ABGR)
            self.graph = self.image.getGraphics()
            self.graph.setRenderingHint(RenderingHints.KEY_ANTIALIASING, RenderingHints.VALUE_ANTIALIAS_ON)
            self.graph.setBackground(Color(1.0, 1.0, 1.0, 0.0))
            self.graph.clearRect(0, 0, 1024, 256)
            self.graph.setColor(Color(1.0, 1.0, 1.0, 0.5))
            self.graph.fillRoundRect(0, 0, 1024, 256, 30, 30)
            self.graph.setFont(Font(FONT_JP, Font.BOLD, 34))
            self.graph.setColor(Color(0.0, 0.0, 0.0, 0.5))
            self.graph.drawString(u'マウスをドラッグして画像の範囲を指定して下さい。', 48, 96)
            self.graph.drawString(u'右クリックでメニューを表示します。', 48, 176)
        else: raise AttributeError

    def __get__(self, this, that):
        if 0.0 < self.size < self.min:
            self.graph.drawString(u'指定領域サイズ：{0:>5,.1f}Kpxは下限サイズを下回っています。'.format(self.size), 36, 96)
            self.graph.drawString(u'{0:,.1f}Kpx以上で再度指定して下さい。'.format(self.min), 36, 176)
        elif self.max < self.size:
            self.graph.drawString(u'指定領域サイズ：{0:>5,.1f}Kpxは上限サイズを超えています。'.format(self.size), 36, 96)
            self.graph.drawString(u'{0:,.1f}Kpx以下で再度指定して下さい。'.format(self.max), 36, 176)
        elif self.min <= self.size <= self.max:
            self.graph.drawString(u'指定領域サイズ：{0:>5,.1f}Kpx'.format(self.size), 128, 96)
            self.graph.drawString(u'右クリックメニューによりセーブできます。', 128, 176)
        return self.image

    def __set__(self, this, pixels):
        self.__dict__['size'] = pixels
        if 0.0 < self.size:
            self.graph.clearRect(0, 0, 1024, 256)
            self.graph.setColor(Color(1.0, 1.0, 1.0, 0.5))
            self.graph.fillRoundRect(0, 0, 1024, 256, 30, 30)
            self.graph.setColor(Color(0.0, 0.0, 0.0, 0.5))
        this.validity = True if self.min <= pixels <= self.max else False

class Overlay(JDialog):
    def __init__(self):
        super(self.__class__, self).__init__()
        self.setLocation(0, 0)
        self.setSize(screenSize)
        self.setUndecorated(True)
        self.setAlwaysOnTop(True)

class CtxMenu(JPopupMenu):
    def __init__(self, label): super(self.__class__, self).__init__(label)
    
    def show(self, client, pointX, pointY):
        panel = self.getInvoker()
        super(self.__class__, self).show(client, pointX, pointY)
        axisX = pointX if pointX < client.width // 2 else pointX - self.width
        axisY = pointY if pointY < client.height // 2 else pointY - self.height
        self.setLocation(axisX, axisY)
        panel.repaint()

ctx = CtxMenu(u'キャプチャメニュー')

class MenuCtrl(JMenuItem):
    def __init__(self, label):
        super(self.__class__, self).__init__(label)
        self.setFont(Font(FONT_JP, Font.PLAIN, 16))
        self.setForeground(Color.DARK_GRAY)
        self.setMargin(Insets(5, 5, 5, 5))
        self.setSize(100, 30)

resetCtrl = MenuCtrl(u'リセット')
resetCtrl.setEnabled(False)
quitCtrl = MenuCtrl(u'セーブ')
quitCtrl.setEnabled(False)

class resetImpl(ActionListener):
    def actionPerformed(self, ev):
        panel = ev.getSource().getParent().getInvoker()
        window = panel.getTopLevelAncestor()
        panel.startX, panel.startY, panel.endX, panel.endY, panel.validity = (0, 0, 0, 0, False)
        panel.repaint()
        ev.getSource().setEnabled(False)
        quitCtrl.setEnabled(False)

resetCtrl.addActionListener(resetImpl())

ctx.add(resetCtrl)
ctx.addSeparator()

cancelCtrl = MenuCtrl(u'キャンセル')

class cancelImpl(ActionListener):
    def actionPerformed(self, ev):
        panel = ev.getSource().getParent().getInvoker()
        window = panel.getTopLevelAncestor()
        window.dispose()
        panel.isBusy, panel.artifact, panel.validity = (False, None, False)

cancelCtrl.addActionListener(cancelImpl())

ctx.add(cancelCtrl)
ctx.addSeparator()

class quitImpl(ActionListener):
    def actionPerformed(self, ev):
        panel = ev.getSource().getParent().getInvoker()
        window = panel.getTopLevelAncestor()
        window.dispose()
        panel.isBusy = False

quitCtrl.addActionListener(quitImpl())
ctx.add(quitCtrl)

class Telop(Runnable):
    def __init__(self, target, action):
        self.client, self.handle = (target, action)

    def run(self):
        panel = self.client
        graph = panel.getGraphics()
        w, h = (panel.getSize().width, panel.getSize().height)
        x, y = ((w-1024)//2, (h-256)//2)
        graph.drawImage(panel.sign, x, y, 1024, 256, None)
        TimeUnit.MILLISECONDS.sleep(1500)
        self.client.addMouseMotionListener(self.client)
        self.client.addMouseListener(self.handle)

class PanelImpl(MouseAdapter):
    def __init__(self):
        super(self.__class__, self).__init__()
 
    def mousePressed(self, ev):
        panel = ev.getSource()
        if not panel.active: panel.active = True
        if ev.getButton() == BUTTON1:
            panel.atWork, panel.color = (True, Color.WHITE)
            point = ev.getPoint()
            panel.startX = panel.endX = point.x
            panel.startY = panel.endY = point.y
            panel.repaint()
        ev.consume()

    def mouseReleased(self, ev):
        if ev.getButton() == BUTTON1:
            panel = ev.getSource()
            point = ev.getPoint()
            if panel.atWork:
                width, height = (abs(panel.endX-panel.startX), abs(panel.endY-panel.startY))
                size = ceil((width * height) / 100.0) / 10.0
                graph = panel.getGraphics()
                panel.color = Color.GREEN.brighter() if panel.minKpx <= size <= panel.maxKpx else Color.MAGENTA.brighter()
                graph.setColor(panel.color)
                if panel.artifact is not None: graph.drawRect(*panel.artifact)
                if 0.0 < size: 
                    panel.active, panel.atWork = (False, False)
                    panel.removeMouseListener(self)
                    panel.removeMouseMotionListener(panel)
                    panel.sign = size
                    resetCtrl.setEnabled(True)
                    quitCtrl.setEnabled(True) if panel.validity else quitCtrl.setEnabled(False)
                    SwingUtilities.invokeLater(Telop(panel, self))
        ev.consume()

pImpl = PanelImpl()

class Content(JPanel, MouseMotionListener, Runnable):
    def __new__(cls, image, guide):
        cls.sign = guide
        return super(cls.__class__, cls).__new__(cls)

    def __init__(self, image, guide):
        super(JPanel, self).__init__(BorderLayout())
        self.setCursor(Cursor(Cursor.CROSSHAIR_CURSOR))
        self.frontend = image
        self.backend = BufferedImage(image.getWidth(), image.getHeight(), image.getType())
        operator = RescaleOp(0.7, 0.0, None)
        operator.filter(image, self.backend)
        self.minKpx, self.maxKpx = (guide.min, guide.max)
        self.isBusy, self.atWork, self.active, self.color, self.validity = (True, False, False, Color.WHITE, False)
        self.startX, self.startY, self.endX, self.endY, self.artifact = (0, 0, 0, 0, None)
        ctx.setInvoker(self)

    def paintComponent(self, graph):
        self.setSize(self.backend.getWidth(), self.backend.getHeight())
        graph.drawImage(self.backend, 0, 0, self.getWidth(), self.getHeight(), None)
        x = self.startX if self.startX < self.endX else self.endX
        y = self.startY if self.startY < self.endY else self.endY
        width, height = (abs(self.endX-self.startX), abs(self.endY-self.startY))
        if 0 < width * height:
            self.artifact = [x, y, width, height]
            image = self.frontend.getSubimage(x, y, width, height)
            graph.drawImage(image, x, y, width, height, None)
            graph.setColor(self.color)
            graph.drawRect(*self.artifact)
        else: self.artifact = None

    def supply(self):
        if self.validity:
            srcImage = self.frontend.getSubimage(*self.artifact)
            dstImage = BufferedImage(srcImage.width, srcImage.height, BufferedImage.TYPE_3BYTE_BGR)
            dstImage.getGraphics().drawImage(srcImage, 0, 0, srcImage.width, srcImage.height, None)
            return dstImage
        else: return None

    def run(self): SwingUtilities.invokeLater(Telop(self, pImpl))

    def mouseDragged(self, ev):
        ev.consume()
        if self.atWork:
            point = ev.getPoint()
            self.endX, self.endY = (point.x, point.y)
            self.repaint()

    def mouseMoved(self, ev):
        ev.consume()
        if not self.active:
            self.active = True
            self.repaint()

    def createToolTip(self):
        tips = super(self.__class__, self).createToolTip()
        tips.setFont(Font(FONT_JP, Font.PLAIN, 16))
        tips.setComponent(self)
        return tips

tipStats = ToolTipManager.sharedInstance()
tipStats.setInitialDelay(2000)
tipStats.setDismissDelay(2000)
tipStats.setReshowDelay(300)

def doRender(minSize, maxSize):
    deskImage = robot.createScreenCapture(Rectangle(screenSize))
    JDialog.setDefaultLookAndFeelDecorated(False)
    overlay = Overlay()
    content = Content(deskImage, Guide(minSize, maxSize))
    content.setComponentPopupMenu(ctx)
    content.setToolTipText(u'ドラッグで範囲 / 右クリックでメニュー表示')
    overlay.add(content, BorderLayout.CENTER)
    overlay.setVisible(True)
    SwingUtilities.invokeLater(content)
    while content.isBusy: TimeUnit.SECONDS.sleep(1)
    return content.supply()
