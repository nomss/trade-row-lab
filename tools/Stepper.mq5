//+------------------------------------------------------------------+
//| Stepper.mq5 — BlindLab play-forward EA                           |
//| Attach to a *_F (live-frozen) or TEST_n (blind) chart.           |
//| Key N = +1 M5 bar, key H = +12 bars (1 hour).                    |
//| No trading functions anywhere in this file.                      |
//+------------------------------------------------------------------+
#property copyright "BlindLab"
#property version   "1.00"

input int InpBarsPerN = 1;    // bars appended on key N
input int InpBarsPerH = 12;   // bars appended on key H

string  g_mode="";       // LIVE / BLIND
string  g_real="";       // real source symbol
long    g_freeze=0;      // freeze time (real/server epoch)
double  g_factor=1.0;
long    g_shift=0;

MqlRates g_buf[];        // blind continuation buffer
int      g_buflen=0;

string HexUnxor(const string hex)
  {
   string r="";
   int n=StringLen(hex);
   for(int i=0;i+1<n;i+=2)
     {
      string b=StringSubstr(hex,i,2);
      int v=(int)StringToInteger("0x"+b);
      r+=CharToString((uchar)(v^0x5A));
     }
   return r;
  }

string ReadText(const string path)
  {
   int h=FileOpen(path,FILE_READ|FILE_TXT|FILE_ANSI);
   if(h==INVALID_HANDLE) return "";
   string s="";
   while(!FileIsEnding(h)) s+=FileReadString(h);
   FileClose(h);
   return s;
  }

int OnInit()
  {
   string sym=_Symbol;
   string key=HexUnxor(ReadText("BlindLab\\key_"+sym+".txt"));
   string p[];
   if(StringSplit(key,'|',p)<5)
     {
      Comment("BlindLab Stepper: no key file for ",sym," — attach to a *_F or TEST_n chart.");
      return(INIT_SUCCEEDED);
     }
   g_mode=p[0]; g_real=p[1];
   g_freeze=StringToInteger(p[2]);
   g_factor=StringToDouble(p[3]);
   g_shift =StringToInteger(p[4]);

   if(g_mode=="BLIND")
     {
      string raw=HexUnxor(ReadText("BlindLab\\buf_"+sym+".txt"));
      string lines[];
      int n=StringSplit(raw,'\n',lines);
      ArrayResize(g_buf,0);
      for(int i=0;i<n;i++)
        {
         string f[];
         if(StringSplit(lines[i],'|',f)<6) continue;
         int k=ArraySize(g_buf); ArrayResize(g_buf,k+1);
         g_buf[k].time =(datetime)StringToInteger(f[0]);
         g_buf[k].open =StringToDouble(f[1]);
         g_buf[k].high =StringToDouble(f[2]);
         g_buf[k].low  =StringToDouble(f[3]);
         g_buf[k].close=StringToDouble(f[4]);
         g_buf[k].tick_volume=StringToInteger(f[5]);
         g_buf[k].spread=0; g_buf[k].real_volume=0;
        }
      g_buflen=ArraySize(g_buf);
     }
   Comment("BlindLab Stepper armed on ",sym,"  [",g_mode,"]  N=+",InpBarsPerN," bar  H=+",InpBarsPerH," bars");
   return(INIT_SUCCEEDED);
  }

void OnDeinit(const int reason){ Comment(""); }

void Append(const int count)
  {
   string sym=_Symbol;
   datetime last=iTime(sym,PERIOD_M5,0);
   if(last==0){ Comment("BlindLab: no bars on ",sym); return; }

   MqlRates add[]; ArrayResize(add,0);

   if(g_mode=="BLIND")
     {
      for(int i=0;i<g_buflen && ArraySize(add)<count;i++)
         if((long)g_buf[i].time>(long)last)
           {
            int k=ArraySize(add); ArrayResize(add,k+1); add[k]=g_buf[i];
           }
      if(ArraySize(add)==0){ Comment("BlindLab: end of hidden buffer — session done. Commit your call."); return; }
     }
   else // LIVE — pull fresh bars from the real symbol
     {
      long realLast=(long)last+g_shift;   // shift is 0 in live mode
      MqlRates rr[];
      int got=CopyRates(g_real,PERIOD_M5,(datetime)(realLast+1),TimeCurrent(),rr);
      if(got<1){ Comment("BlindLab: market has no new bars yet for ",g_real); return; }
      int dig=(int)SymbolInfoInteger(sym,SYMBOL_DIGITS);
      for(int i=0;i<got && ArraySize(add)<count;i++)
        {
         if((long)rr[i].time<=realLast) continue;
         int k=ArraySize(add); ArrayResize(add,k+1);
         add[k]=rr[i];
         add[k].time=(datetime)((long)rr[i].time-g_shift);
         add[k].open =NormalizeDouble(rr[i].open *g_factor,dig);
         add[k].high =NormalizeDouble(rr[i].high *g_factor,dig);
         add[k].low  =NormalizeDouble(rr[i].low  *g_factor,dig);
         add[k].close=NormalizeDouble(rr[i].close*g_factor,dig);
         add[k].spread=0;
        }
      if(ArraySize(add)==0){ Comment("BlindLab: caught up to live — nothing new yet."); return; }
     }

   if(CustomRatesUpdate(sym,add)>0)
      Comment("BlindLab [",g_mode,"] advanced to ",TimeToString(add[ArraySize(add)-1].time,TIME_DATE|TIME_MINUTES));
   else
      Comment("BlindLab: CustomRatesUpdate failed err=",GetLastError());
  }

void OnChartEvent(const int id,const long &lparam,const double &dparam,const string &sparam)
  {
   if(id!=CHARTEVENT_KEYDOWN) return;
   if(lparam=='N' || lparam=='n') Append(InpBarsPerN);
   if(lparam=='H' || lparam=='h') Append(InpBarsPerH);
  }
//+------------------------------------------------------------------+
