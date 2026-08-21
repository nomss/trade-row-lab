//+------------------------------------------------------------------+
//| Freezer.mq5 — BlindLab chart freezer                             |
//| LIVE  : snapshots each watch symbol as SYM_F frozen at "now"     |
//| BLIND : random symbol+day, scaled & date-shifted, as TEST_n      |
//| No trading functions anywhere in this file.                      |
//+------------------------------------------------------------------+
#property copyright "BlindLab"
#property version   "1.00"
#property script_show_inputs

enum ENUM_FREEZE_MODE { MODE_LIVE=0, MODE_BLIND=1, MODE_LIVE_BLIND=2 };

input ENUM_FREEZE_MODE InpMode          = MODE_BLIND;
input string  InpSymbols                = "NASUSD,U30USD,SPXUSD,XAUUSD,USOUSD,EURUSD,GBPUSD,USDCAD,USDJPY,AUDUSD";
input int     InpFreezeServerHour       = 16;    // blind freeze: 16:30 server = 9:30 AM EST (Coinexx)
input int     InpFreezeServerMin        = 30;
input int     InpContextDays            = 60;    // visible history before the freeze
input int     InpFutureHours            = 30;    // hidden continuation (blind mode)
input int     InpKeepTests              = 30;    // keep newest N TEST symbols, delete older
input int     InpDeckProb               = 70;    // % of blind rounds drawn from own-trade-day deck
input int     InpBlindCount             = 10;    // blind charts created per run

//--- xor-hex encoding for key/buffer files (casual-open protection only)
string XorHex(const string s)
  {
   string r="";
   for(int i=0;i<StringLen(s);i++)
      r+=StringFormat("%02X",(int)(StringGetCharacter(s,i)^0x5A));
   return r;
  }

bool WriteText(const string path,const string content)
  {
   int h=FileOpen(path,FILE_WRITE|FILE_TXT|FILE_ANSI);
   if(h==INVALID_HANDLE){ Print("BlindLab: cannot write ",path," err=",GetLastError()); return false; }
   FileWriteString(h,content);
   FileClose(h);
   return true;
  }

int SplitSymbols(string &out[])
  {
   string parts[];
   int n=StringSplit(InpSymbols,',',parts);
   ArrayResize(out,0);
   for(int i=0;i<n;i++)
     {
      string s=parts[i];
      StringTrimLeft(s); StringTrimRight(s);
      if(s=="") continue;
      if(!SymbolSelect(s,true)){ Print("BlindLab: symbol not found: ",s); continue; }
      int k=ArraySize(out); ArrayResize(out,k+1); out[k]=s;
     }
   return ArraySize(out);
  }

bool DisguiseAndReplace(const string custom,MqlRates &src[],const double factor,const long shiftSec,const int digits)
  {
   int n=ArraySize(src);
   if(n<=0) return false;
   MqlRates dst[];
   ArrayResize(dst,n);
   for(int i=0;i<n;i++)
     {
      dst[i]=src[i];
      dst[i].time =(datetime)((long)src[i].time - shiftSec);
      dst[i].open =NormalizeDouble(src[i].open *factor,digits);
      dst[i].high =NormalizeDouble(src[i].high *factor,digits);
      dst[i].low  =NormalizeDouble(src[i].low  *factor,digits);
      dst[i].close=NormalizeDouble(src[i].close*factor,digits);
      dst[i].spread=0;
     }
   long total=CustomRatesReplace(custom,dst[0].time,dst[n-1].time,dst);
   return(total>0);
  }

bool MakeCustom(const string name,const string origin)
  {
   ResetLastError();
   if(!CustomSymbolCreate(name,"BlindLab",origin))
     {
      if(GetLastError()!=5300 && GetLastError()!=4301 && GetLastError()!=5304)
         Print("BlindLab: CustomSymbolCreate(",name,") err=",GetLastError());
      // may already exist — that is fine for LIVE (we recreate data below)
     }
   // scrub identity leaks copied from the origin symbol
   CustomSymbolSetString(name,SYMBOL_DESCRIPTION,"Blind chart");
   CustomSymbolSetString(name,SYMBOL_CURRENCY_BASE,"XXX");
   CustomSymbolSetString(name,SYMBOL_CURRENCY_PROFIT,"USD");
   CustomSymbolSetString(name,SYMBOL_CURRENCY_MARGIN,"USD");
   CustomSymbolSetString(name,SYMBOL_ISIN,"");
   CustomSymbolSetString(name,SYMBOL_PATH,"BlindLab\\"+name);
   return SymbolSelect(name,true);
  }

int HexDigit(const ushort c)
  {
   if(c>='0' && c<='9') return (int)(c-'0');
   if(c>='A' && c<='F') return (int)(c-'A')+10;
   if(c>='a' && c<='f') return (int)(c-'a')+10;
   return -1;
  }

string HexUnxor(const string hex)
  {
   string r="";
   int n=StringLen(hex);
   for(int i=0;i+1<n;i+=2)
     {
      int hi=HexDigit(StringGetCharacter(hex,i));
      int lo=HexDigit(StringGetCharacter(hex,i+1));
      if(hi<0 || lo<0) continue;
      r+=CharToString((uchar)((hi*16+lo)^0x5A));
     }
   return r;
  }

int LoadDeck(string &out[])
  {
   // deck.txt: one xor-hex-encoded entry per line ("SYMBOL|YYYY.MM.DD")
   int h=FileOpen("BlindLab\\deck.txt",FILE_READ|FILE_TXT|FILE_ANSI);
   if(h==INVALID_HANDLE) return 0;
   ArrayResize(out,0);
   while(!FileIsEnding(h))
     {
      string line=FileReadString(h);
      if(StringLen(line)<12) continue;
      string entry=HexUnxor(line);
      if(StringLen(entry)<8 || StringFind(entry,"|")<1) continue;
      int k=ArraySize(out); ArrayResize(out,k+1); out[k]=entry;
     }
   FileClose(h);
   return ArraySize(out);
  }

//--- find next free TEST index and clean old ones
int NextTestIndex()
  {
   int last=0;
   for(int i=1;i<=2000;i++)
      if(SymbolInfoInteger("TEST_"+(string)i,SYMBOL_CUSTOM)) last=i;
   // cleanup
   for(int i=1;i<=last-InpKeepTests;i++)
     {
      string nm="TEST_"+(string)i;
      if(SymbolInfoInteger(nm,SYMBOL_CUSTOM))
        {
         SymbolSelect(nm,false);
         CustomSymbolDelete(nm);
        }
     }
   return last+1;
  }

void DoLive(const bool blind)
  {
   string syms[];
   int n=SplitSymbols(syms);
   datetime freeze=TimeCurrent();
   // shuffled letter assignment for blind-live
   int order[]; ArrayResize(order,n);
   for(int i=0;i<n;i++) order[i]=i;
   MathSrand((int)TimeLocal()+(int)GetTickCount());
   for(int i=n-1;i>0;i--){ int j=MathRand()%(i+1); int tmp=order[i]; order[i]=order[j]; order[j]=tmp; }
   long weeks=((long)freeze-(long)D'2023.06.05 00:00')/(7*86400);
   long liveShift=weeks*7*86400;
   int done=0;
   for(int i=0;i<n;i++)
     {
      string src=syms[order[i]];
      string dst=blind ? ("LIVE_"+StringSubstr("ABCDEFGHIJKLMNOP",i,1)) : (src+"_F");
      double factor=1.0; long shiftSec=0;
      if(blind)
        {
         factor=NormalizeDouble(MathPow(10.0,((double)MathRand()/32768.0)*0.85-0.45),4);
         shiftSec=liveShift;
        }
      int digits=(int)SymbolInfoInteger(src,SYMBOL_DIGITS);
      MqlRates rates[];
      datetime from=freeze-(long)InpContextDays*86400;
      int got=CopyRates(src,PERIOD_M5,from,freeze,rates);
      if(got<100){ Print("BlindLab: not enough M5 history for ",src," got=",got); continue; }
      if(!MakeCustom(dst,src)) continue;
      CustomSymbolSetInteger(dst,SYMBOL_DIGITS,digits);   // dst may be reused by a different instrument tomorrow
      // wipe stale bars outside the new window (previous day / previous instrument)
      CustomRatesDelete(dst,0,(datetime)((long)from-shiftSec-1));
      CustomRatesDelete(dst,(datetime)((long)freeze-shiftSec+1),(datetime)((long)freeze-shiftSec+400*86400));
      if(!DisguiseAndReplace(dst,rates,factor,shiftSec,digits)) { Print("BlindLab: rates failed ",dst); continue; }
      string key="LIVE|"+src+"|"+(string)(long)freeze+"|"+DoubleToString(factor,4)+"|"+(string)shiftSec;
      WriteText("BlindLab\\key_"+dst+".txt",XorHex(key));
      done++;
     }
   if(blind)
      Alert("BlindLab LIVE-BLIND: ",done," anonymized charts LIVE_A.. ready. No peeking at real charts until calls are committed!");
   else
      Alert("BlindLab LIVE freeze done: ",done," symbols frozen at ",TimeToString(freeze,TIME_DATE|TIME_MINUTES),
            " — open the *_F charts. Stepper key N = +5min from real feed.");
  }

void DoBlind()
  {
   string syms[];
   int n=SplitSymbols(syms);
   if(n==0){ Alert("BlindLab: no valid symbols"); return; }
   MathSrand((int)TimeLocal()+(int)GetTickCount());
   string deckArr[];
   int deckN=LoadDeck(deckArr);
   bool fromDeck=false;
   int made=0;
   string names="";
   for(int round=0;round<InpBlindCount;round++)
   for(int attempt=0;attempt<300;attempt++)
     {
      string src="";
      datetime freeze=0;
      fromDeck=(deckN>0 && (MathRand()%100)<InpDeckProb);
      if(fromDeck)
        {
         string df[];
         if(StringSplit(deckArr[MathRand()%deckN],'|',df)<2) continue;
         src=df[0];
         StringTrimLeft(src); StringTrimRight(src);
         if(!SymbolSelect(src,true)) continue;
         datetime day0=StringToTime(df[1]);
         if(day0<=0) continue;
         freeze=(datetime)((long)day0+(long)InpFreezeServerHour*3600+(long)InpFreezeServerMin*60);
        }
      else
        {
         src=syms[MathRand()%n];
         int total0=Bars(src,PERIOD_M5);
         if(total0<20000) continue;
         int idx=(int)(( (double)MathRand()/32768.0 )*(total0-9000))+3000;   // random bar, away from both ends
         datetime t[];
         if(CopyTime(src,PERIOD_M5,idx,1,t)!=1) continue;
         MqlDateTime dt; TimeToStruct(t[0],dt);
         if(dt.day_of_week<1 || dt.day_of_week>5) continue;
         dt.hour=InpFreezeServerHour; dt.min=InpFreezeServerMin; dt.sec=0;
         freeze=StructToTime(dt);
        }
      int digits=(int)SymbolInfoInteger(src,SYMBOL_DIGITS);
      int total=Bars(src,PERIOD_M5);
      if(total<5000) continue;
      datetime ctxFrom=freeze-(long)InpContextDays*86400;
      datetime futTo  =freeze+(long)InpFutureHours*3600;
      datetime firstBar[]; datetime lastBar[];
      if(CopyTime(src,PERIOD_M5,total-1,1,firstBar)!=1) continue;
      if(CopyTime(src,PERIOD_M5,0,1,lastBar)!=1) continue;
      if(ctxFrom<firstBar[0] || futTo>lastBar[0]) continue;

      MqlRates ctx[];
      if(CopyRates(src,PERIOD_M5,ctxFrom,freeze,ctx)<1000) continue;
      MqlRates fut[];
      if(CopyRates(src,PERIOD_M5,(datetime)((long)freeze+1),futTo,fut)<12) continue;

      // disguise parameters
      double factor=MathPow(10.0,((double)MathRand()/32768.0)*0.85-0.45);   // ~0.35 .. 2.5
      factor=NormalizeDouble(factor,4);
      long weeks=((long)freeze-(long)D'2023.06.05 00:00')/(7*86400);
      long shiftSec=weeks*7*86400;                                          // lands week of 2023-06-05, weekday kept

      int tn=NextTestIndex();
      string dst="TEST_"+(string)tn;
      if(!MakeCustom(dst,src)) continue;
      if(!DisguiseAndReplace(dst,ctx,factor,shiftSec,digits)) continue;

      // hidden continuation buffer (disguised, encoded)
      string buf="";
      for(int i=0;i<ArraySize(fut);i++)
         buf+=(string)((long)fut[i].time-shiftSec)+"|"+
              DoubleToString(NormalizeDouble(fut[i].open *factor,digits),digits)+"|"+
              DoubleToString(NormalizeDouble(fut[i].high *factor,digits),digits)+"|"+
              DoubleToString(NormalizeDouble(fut[i].low  *factor,digits),digits)+"|"+
              DoubleToString(NormalizeDouble(fut[i].close*factor,digits),digits)+"|"+
              (string)fut[i].tick_volume+"\n";
      WriteText("BlindLab\\buf_"+dst+".txt",XorHex(buf));

      string key="BLIND|"+src+"|"+(string)(long)freeze+"|"+DoubleToString(factor,4)+"|"+(string)shiftSec+"|"+(fromDeck?"DECK":"RAND");
      WriteText("BlindLab\\key_"+dst+".txt",XorHex(key));

      made++; names+=dst+"  ";
      ChartOpen(dst,PERIOD_M5);
      break;
     }
   if(made>0)
      Alert("BlindLab: ",made," blind charts ready [deck: ",deckN,"]  ",names);
   else
      Alert("BlindLab: could not build any blind chart (not enough M5 history?)");
  }

void OnStart()
  {
   if(InpMode==MODE_LIVE)            DoLive(false);
   else if(InpMode==MODE_LIVE_BLIND) DoLive(true);
   else                              DoBlind();
  }
//+------------------------------------------------------------------+
